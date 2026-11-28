from __future__ import annotations

import functools
import numbers
import sys
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
        if by is not MISSING and equal(by, 0):
            raise TypeError(f"changes() with by={by!r} asserts no change; use unchanged()")

        self._get = _resolve_getter(getter, attr)
        if label is not None:
            self.label = label
        else:
            self._pending_label = _label.Pending(getter, attr)
        self._expect_change = expect_change
        self._to = to
        self._by = by
        self._before: Any = MISSING
        self._after: Any = MISSING
        self._site = _caller_site()
        self._entered = False

    def __del__(self) -> None:
        # like an un-awaited coroutine: without `with`, nothing is ever checked
        if getattr(self, "_entered", True):
            return
        name = "changes" if self._expect_change else "unchanged"
        filename, lineno, module = self._site
        warnings.warn_explicit(
            f"{name}() was never entered, so it asserts nothing: use it in a with statement",
            ChangeWarning,
            filename,
            lineno,
            module,
        )

    @functools.cached_property
    def label(self) -> str:
        """Names the expression in failure messages; read from source only when first needed."""
        return self._pending_label.resolve()

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
            raise AttributeError("after isn't set: it's read when the with block exits")
        return self._after

    @property
    def delta(self) -> Any:
        """`len(after) - len(before)` for values with a length, else `after - before`."""
        return self._delta("delta")[0]

    def _delta(self, needed_by: str) -> tuple[Any, bool]:
        """The delta, and whether it counts items."""
        __tracebackhide__ = True
        after, before = self.after, self.before
        # length first: sets subtract too, but by=1 means one more item
        try:
            return len(after) - len(before), True
        except TypeError:
            pass
        try:
            return after - before, False
        except TypeError:
            raise TypeError(
                f"{self.label}: {needed_by} needs values with a length or that subtract "
                f"({type(after).__name__} - {type(before).__name__} failed)"
            ) from None

    def __enter__(self) -> Self:
        __tracebackhide__ = True
        self._entered = True
        # after is read and compared at once, so only before needs protecting from the block
        value = self._read("before the block")
        try:
            self._before, self._holds_identity = snapshot(value)
        except Incomparable:
            raise self._incomparable(value) from None
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        __tracebackhide__ = True
        # an inner context's failure isn't the block raising: check, and merge into it
        if exc is not None and not isinstance(exc, ChangeAssertionError):
            # what pytest.raises is used for; pytest outcomes and KeyboardInterrupt end the test
            if isinstance(exc, Exception | SystemExit):
                name = "changes" if self._expect_change else "unchanged"
                error = type(exc).__name__
                warnings.warn(
                    f"{self.label}: not checked because the block raised {error}: put the "
                    f"expectation outside pytest.raises: with {name}(...), pytest.raises({error}):",
                    ChangeWarning,
                    stacklevel=2,
                )
            return

        self._after = self._read("after the block")
        try:
            detail = self._check()
            hint = self._identity_hint()
        except Incomparable:
            raise self._incomparable(self._after) from None
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

    def _identity_hint(self) -> str | None:
        """Why a before/after comparison may be judging identity rather than state."""
        if self._to is not MISSING or self._by is not MISSING:
            return None
        before, after = self._before, self._after
        kind = type(before).__name__
        by_identity = type(before).__eq__ is object.__eq__
        fix = "write a getter for the state you mean"
        if equal(before, after):
            if by_identity:
                return (
                    f"{kind} compares by identity, so changes to its attributes are invisible: "
                    f"{fix}, e.g. lambda: vars({self.label})"
                )
            if self._holds_identity:
                return (
                    f"{kind} holds values that compare by identity, "
                    f"so changes to their attributes are invisible: {fix}"
                )
        elif by_identity and type(after) is type(before):
            return (
                f"{kind} compares by identity, so a fresh object counts as a change even if "
                f"its state is the same: {fix}, e.g. lambda: vars({self.label})"
            )
        return None

    def _incomparable(self, value: Any) -> TypeError:
        return TypeError(
            f"{self.label}: {type(value).__name__} doesn't compare to a bool; "
            "return a comparable value from the getter, such as a list or tuple"
        )

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
            if changed and equal(self._to, after):
                return None
            if not changed and equal(self._to, after):
                short = _plugin.short_repr
                return f"expected to change to {short(self._to)}, but it was already {short(after)}"
            r, explanation = _plugin.compare(after, self._to)
            return _explained(f"expected → {r(self._to)}, {self._actual(changed, r)}", explanation)

        return None if changed else f"expected to change, stayed {_plugin.short_repr(before)}"

    def _check_delta(self) -> str | None:
        __tracebackhide__ = True
        delta, counts = self._delta("by=")
        by = self._by
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


def _caller_site() -> tuple[str, int, str]:
    frame = sys._getframe(1)
    while frame.f_back is not None and _label._in_package(frame.f_globals.get("__name__")):
        frame = frame.f_back
    return frame.f_code.co_filename, frame.f_lineno, frame.f_globals.get("__name__", "")


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
    # deltas read as amounts (+5, 1:00:00); strings keep quotes, since the type is the point
    if isinstance(value, numbers.Number) and not isinstance(value, bool):
        try:
            return format(value, "+")
        except (TypeError, ValueError):
            pass
    return repr(value) if isinstance(value, (str, bytes)) else str(value)


def _explained(headline: str, explanation: list[str]) -> str:
    return "\n".join([headline, *explanation])


def _indent(text: str, prefix: str) -> str:
    # continuation lines sit under their own headline, so stacked failures stay apart
    return text.replace("\n", "\n" + prefix)
