from __future__ import annotations

import numbers
from collections.abc import Callable
from types import TracebackType
from typing import Any, Self

from . import _label, _plugin
from ._snapshot import snapshot


class _Missing:
    def __repr__(self) -> str:
        return "MISSING"


MISSING: Any = _Missing()


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
        by_at_least: Any = MISSING,
        by_at_most: Any = MISSING,
        label: str | None = None,
    ):
        given = {
            name
            for name, value in [
                ("to", to),
                ("by", by),
                ("by_at_least", by_at_least),
                ("by_at_most", by_at_most),
            ]
            if value is not MISSING
        }
        for conflict in [{"to", "by"}, {"to", "by_at_least"}, {"to", "by_at_most"}]:
            if conflict <= given:
                raise TypeError(f"changes() cannot combine {' and '.join(sorted(conflict))}")
        if "by" in given and given & {"by_at_least", "by_at_most"}:
            raise TypeError("changes() cannot combine by with by_at_least or by_at_most")

        self._get, default_label = _resolve_getter(getter, attr)
        self.label = label if label is not None else default_label
        self._expect_change = expect_change
        self._to = to
        self._by = by
        self._by_at_least = by_at_least
        self._by_at_most = by_at_most
        self.before: Any = MISSING
        self.after: Any = MISSING

    @property
    def delta(self) -> Any:
        """`after - before`, or MISSING when the values can't be subtracted."""
        try:
            return self.after - self.before
        except TypeError:
            return MISSING

    def __enter__(self) -> Self:
        __tracebackhide__ = True
        # after is read and compared at once, so only before needs protecting from the block
        self.before = snapshot(self._read("before the block"))
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        __tracebackhide__ = True
        if exc is not None and not isinstance(exc, ChangeAssertionError):
            return

        self.after = self._read("after the block completed")
        detail = self._check()
        if detail is None:
            return
        if exc is not None:
            # inner contexts exit first, so prepending keeps source order
            exc.failures.insert(0, (self.label, detail))
            return
        raise ChangeAssertionError(self.label, detail)

    def _read(self, when: str) -> Any:
        try:
            return self._get()
        except Exception as e:
            e.add_note(f"raised by the getter for {self.label} {when}")
            raise

    def _check(self) -> str | None:
        before, after = self.before, self.after
        changed = before != after

        if not self._expect_change:
            if not changed:
                return None
            r, explanation = _plugin.compare(after, before)
            return _explained(f"expected no change, got {self._transition(r)}", explanation)

        if (
            self._by is not MISSING
            or self._by_at_least is not MISSING
            or self._by_at_most is not MISSING
        ):
            return self._check_delta()

        if self._to is not MISSING:
            if changed and self._to == after:
                return None
            r, explanation = _plugin.compare(after, self._to)
            return _explained(f"expected → {r(self._to)}, {self._actual(changed, r)}", explanation)

        return None if changed else f"expected to change, stayed {before!r}"

    def _check_delta(self) -> str | None:
        try:
            delta = self.after - self.before
        except TypeError as e:
            raise TypeError(
                f"{self.label}: by= needs after - before, which failed for "
                f"{type(self.before).__name__} and {type(self.after).__name__}"
            ) from e

        if self._by is not MISSING:
            ok = self._by == delta
            expected = f"Δ {_signed(self._by)}"
        else:
            least, most = self._by_at_least, self._by_at_most
            ok = (least is MISSING or delta >= least) and (most is MISSING or delta <= most)
            if least is not MISSING and most is not MISSING:
                expected = f"{_signed(least)} ≤ Δ ≤ {_signed(most)}"
            elif least is not MISSING:
                expected = f"Δ ≥ {_signed(least)}"
            else:
                expected = f"Δ ≤ {_signed(most)}"

        if ok:
            return None
        if self.before != self.after:
            return f"expected {expected}, got Δ {_signed(delta)} ({self.before!r} → {self.after!r})"
        return f"expected {expected}, did not change (stayed {self.before!r})"

    def _actual(self, changed: bool, r: Callable[[Any], str]) -> str:
        return f"got {self._transition(r)}" if changed else f"stayed {r(self.before)}"

    def _transition(self, r: Callable[[Any], str]) -> str:
        text = f"{r(self.before)} → {r(self.after)}"
        delta = self.delta
        if isinstance(delta, numbers.Number) and not isinstance(delta, bool):
            text += f" (Δ {_signed(delta)})"
        return text


def changes(
    getter: Any,
    attr: str | None = None,
    *,
    to: Any = MISSING,
    by: Any = MISSING,
    by_at_least: Any = MISSING,
    by_at_most: Any = MISSING,
    label: str | None = None,
) -> ChangeContext:
    """Assert that the block changes `getter()`, or `getattr(getter, attr)` when attr is given."""
    return ChangeContext(
        getter,
        attr,
        expect_change=True,
        to=to,
        by=by,
        by_at_least=by_at_least,
        by_at_most=by_at_most,
        label=label,
    )


def unchanged(getter: Any, attr: str | None = None, *, label: str | None = None) -> ChangeContext:
    """Assert that the block leaves `getter()` (or `getattr(getter, attr)`) equal to before."""
    return ChangeContext(getter, attr, expect_change=False, label=label)


def _resolve_getter(getter: Any, attr: str | None) -> tuple[Callable[[], Any], str]:
    # attr given means object form, even when the object is itself callable (e.g. a Mock)
    if attr is not None:
        return (lambda: getattr(getter, attr)), _label.label(getter, attr)

    if not callable(getter):
        raise TypeError(
            f"changes() needs a callable getter or an object and attribute name, "
            f"got {type(getter).__name__}"
        )
    return getter, _label.label(getter, None)


def _signed(value: Any) -> str:
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
