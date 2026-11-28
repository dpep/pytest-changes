from __future__ import annotations

import functools
import numbers
import warnings
from collections.abc import Callable
from types import TracebackType
from typing import Any, Self

from . import _label, _plugin
from ._snapshot import Incomparable, equal, snapshot


class _Missing:
    def __repr__(self) -> str:
        return "MISSING"


MISSING: Any = _Missing()


class ChangeWarning(RuntimeWarning):
    """A change expectation that can't assert what it appears to."""


class ChangeAssertionError(AssertionError):
    """One or more change expectations failed; stacked contexts share one error."""

    def __init__(self, label: str, detail: str):
        super().__init__()
        self.failures: list[tuple[str, str]] = [(label, detail)]

    def __str__(self) -> str:
        if len(self.failures) == 1:
            label, detail = self.failures[0]
            return f"{label}: {_indent(detail, '  ')}"
        width = max(len(label) for label, _ in self.failures)
        lines = [f"{len(self.failures)} change expectations failed"]
        lines += [
            f"  ✗ {label.ljust(width)}  {_indent(detail, ' ' * (width + 6))}"
            for label, detail in self.failures
        ]
        return "\n".join(lines)


class ChangeContext:
    def __init__(
        self,
        getter: Any,
        attr: str | None,
        *,
        expect_change: bool,
        to: Any = MISSING,
        by: Any = MISSING,
        label: str | None = None,
    ):
        if to is not MISSING and by is not MISSING:
            raise TypeError("changes() cannot combine to and by")
        if isinstance(by, range) and not by:
            raise ValueError(f"changes() with by={by!r} can never pass: {by!r} is empty")

        self._get = _resolve_getter(getter, attr)
        self._site = _label.call_site()
        if label is not None:
            self.label = label
        else:
            self._label_args = (getter, attr)
        self._expect_change = expect_change
        self._to = to
        self._by = by
        self._before: Any = MISSING
        self._after: Any = MISSING
        self._after_unset = "it's read when the with block exits"
        self._entered = False
        self._active = False
        self._skipped_by: str | None = None
        _plugin.track(self)

    def warn_if_unchecked(self) -> None:
        """Called by the plugin when a test returns: like an un-awaited coroutine, it checked nothing."""
        if not self._entered:
            message = f"{self._name}() was never entered, so it asserts nothing: use it in a with statement"
        elif self._skipped_by is not None:
            error = self._skipped_by
            message = (
                f"{self.label}: wasn't checked because the block raised {error}: put the "
                f"expectation outside pytest.raises: with {self._name}(...), pytest.raises({error}):"
            )
        else:
            return
        warnings.warn_explicit(message, ChangeWarning, *_label.location(self._site))

    @property
    def _name(self) -> str:
        return "changes" if self._expect_change else "unchanged"

    @functools.cached_property
    def label(self) -> str:
        """Names the expression in failure messages; read from source only when first needed."""
        return _label.label(*self._label_args, self._site)

    @property
    def before(self) -> Any:
        """The value read (and snapshotted) when the block was entered."""
        if self._before is MISSING:
            raise AttributeError("before isn't set: it's read when the with block is entered")
        return self._before

    @property
    def after(self) -> Any:
        """The value read when the block exited."""
        if self._after is MISSING:
            raise AttributeError(f"after isn't set: {self._after_unset}")
        return self._after

    @property
    def delta(self) -> Any:
        """`after - before`, or `len(after) - len(before)` for values that don't subtract."""
        return self._delta("delta", count=False)[0]

    def _delta(self, needed_by: str, count: bool) -> tuple[Any, bool]:
        """The delta, and whether it counts items; `count` tries lengths before subtracting."""
        __tracebackhide__ = True
        after, before = self.after, self.before
        try:
            lengths = len(after) - len(before)
        except TypeError:
            lengths = None
        if count and lengths is not None:
            return lengths, True
        try:
            return after - before, False
        except TypeError:
            if lengths is not None:
                return lengths, True
            raise TypeError(
                f"{self.label}: {needed_by} needs values with a length or that subtract "
                f"({type(after).__name__} - {type(before).__name__} failed)"
            ) from None

    def __enter__(self) -> Self:
        __tracebackhide__ = True
        if self._active:
            raise RuntimeError(
                f"{self._name}() is already in a with block: "
                f"call {self._name}() again for a nested one"
            )
        # each block is checked afresh, so a context can be reused one block at a time
        self._entered = True
        self._skipped_by = None
        self._before = self._after = MISSING
        self._after_unset = "it's read when the with block exits"
        # after is read and compared at once, so only before needs protecting from the block
        value = self._read("before the block")
        try:
            self._before, self._complete = snapshot(value)
        except Incomparable:
            raise self._incomparable(value) from None
        self._active = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        __tracebackhide__ = True
        self._active = False
        # an inner context's failure isn't the block raising: check, and merge into it
        if exc is not None and not isinstance(exc, ChangeAssertionError):
            self._after_unset = "it wasn't read because the block raised"
            self._skipped_by = type(exc).__name__
            return

        self._after = self._read("after the block")
        try:
            detail = self._check()
        except Incomparable as e:
            # chained from an inner context's failure, so it stays visible
            raise self._incomparable(self._after, *e.args) from exc
        hint = self._copy_hint()
        if detail is None:
            if hint is not None:
                warnings.warn(f"{self.label}: {hint}", ChangeWarning, stacklevel=2)
            return
        if hint is not None:
            detail += "\n" + hint
        if exc is not None:
            # inner contexts exit first, so prepending keeps source order
            exc.failures.insert(0, (self.label, detail))
            return
        raise ChangeAssertionError(self.label, detail)

    def _copy_hint(self) -> str | None:
        """Without to= or by=, an incomplete snapshot means the comparison may miss the point."""
        if self._complete or self._to is not MISSING or self._by is not MISSING:
            return None
        return (
            f"couldn't fully copy {type(self._before).__name__}, so the comparison may not "
            "reflect its contents: write a getter for the state you mean"
        )

    def _incomparable(self, value: Any, reason: str | None = None) -> TypeError:
        reason = reason or (
            f"{type(value).__name__} doesn't compare to a bool; "
            "return a comparable value from the getter, such as a list or tuple"
        )
        return TypeError(f"{self.label}: {reason}")

    def _read(self, when: str) -> Any:
        try:
            return self._get()
        except Exception as e:
            e.add_note(f"raised by the getter for {self.label} {when}")
            raise

    def _check(self) -> str | None:
        __tracebackhide__ = True
        before, after = self._before, self._after
        changed = not equal(before, after)

        if not self._expect_change:
            if not changed:
                return None
            r, explanation = _plugin.compare(after, before)
            return _explained(f"expected no change, got {self._transition(r)}", explanation)

        if self._by is not MISSING:
            return self._check_delta()

        if self._to is not MISSING:
            try:
                reached = equal(self._to, after)
            except Incomparable:
                raise Incomparable(
                    f"to= {type(self._to).__name__} doesn't compare to a bool; "
                    "pass a comparable to= value, such as a list or tuple"
                ) from None
            if reached and changed:
                return None
            if reached:
                short = _plugin.short_repr
                return f"expected to change to {short(self._to)}, but it was already {short(after)}"
            r, explanation = _plugin.compare(after, self._to)
            return _explained(f"expected → {r(self._to)}, {self._actual(changed, r)}", explanation)

        return None if changed else f"expected to change, stayed {_plugin.short_repr(before)}"

    def _check_delta(self) -> str | None:
        __tracebackhide__ = True
        by = self._by
        # by=1 on a set means one more item, not a set difference
        delta, counts = self._delta("by=", count=isinstance(by, numbers.Number | range))
        if isinstance(by, range) and not isinstance(delta, numbers.Integral):
            # an interval check would read as a contradiction: "Δ in 1..2, got Δ +1.5"
            raise TypeError(
                f"{self.label}: by={by!r} needs whole-number deltas; "
                "for other values assert on c.delta"
            )
        if delta in by if isinstance(by, range) else equal(by, delta):
            return None
        if isinstance(by, range) and by.step == 1:
            expected = f"Δ in {by.start}..{by.stop - 1}"
        elif isinstance(by, range):
            expected = f"Δ in {by!r}"
        else:
            expected = f"Δ {_signed(by)}"
        if counts:
            before, after = len(self.before), len(self.after)
        else:
            before, after = _plugin.short_repr(self.before), _plugin.short_repr(self.after)
        if not equal(self.before, self.after):
            transition = f"len {before} → {after}" if counts else f"{before} → {after}"
            return f"expected {expected}, got Δ {_signed(delta)} ({transition})"
        stayed = f"len stayed {before}" if counts else f"stayed {before}"
        return f"expected {expected}, did not change ({stayed})"

    def _actual(self, changed: bool, r: Callable[[Any], str]) -> str:
        return f"got {self._transition(r)}" if changed else f"stayed {r(self.before)}"

    def _transition(self, r: Callable[[Any], str]) -> str:
        return f"{r(self.before)} → {r(self.after)}"


def changes(
    getter: Any,
    attr: str | None = None,
    /,
    *,
    to: Any = MISSING,
    by: Any = MISSING,
    label: str | None = None,
) -> ChangeContext:
    """Assert that the block changes `getter()`, or `getattr(getter, attr)` when attr is given."""
    return ChangeContext(getter, attr, expect_change=True, to=to, by=by, label=label)


def unchanged(
    getter: Any, attr: str | None = None, /, *, label: str | None = None
) -> ChangeContext:
    """Assert that the block leaves `getter()` (or `getattr(getter, attr)`) equal to before."""
    return ChangeContext(getter, attr, expect_change=False, label=label)


def _resolve_getter(getter: Any, attr: str | None) -> Callable[[], Any]:
    # attr given means object form, even when the object is itself callable (e.g. a Mock)
    if attr is not None:
        return lambda: getattr(getter, attr)

    if not callable(getter):
        raise TypeError(
            f"changes() needs a callable getter or an object and attribute name, "
            f"got {type(getter).__name__}"
        )
    return getter


def _signed(value: Any) -> str:
    # numbers read as amounts (+5); anything else as its repr, like the values beside it
    if isinstance(value, numbers.Number) and not isinstance(value, bool):
        try:
            return format(value, "+")
        except (TypeError, ValueError):
            pass
    return repr(value)


def _explained(headline: str, explanation: list[str]) -> str:
    return "\n".join([headline, *explanation])


def _indent(text: str, prefix: str) -> str:
    # continuation lines sit under their own headline, so stacked failures stay apart
    return text.replace("\n", "\n" + prefix)
