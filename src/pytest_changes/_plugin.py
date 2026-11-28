"""pytest plugin: explain failed comparisons the way a failed `assert` would."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

# a stack, so an in-process nested run (pytester) restores the outer config on exit
_configs: list[pytest.Config] = []


def pytest_configure(config: pytest.Config) -> None:
    _configs.append(config)


def pytest_unconfigure(config: pytest.Config) -> None:
    _configs.remove(config)


# contexts constructed by each running test function, innermost (pytester) run last
_constructed: list[list[Any]] = []


def track(context: Any) -> None:
    if _constructed:
        _constructed[-1].append(context)


@pytest.hookimpl(wrapper=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> Any:
    contexts: list[Any] = []
    _constructed.append(contexts)
    try:
        result = yield
    finally:
        _constructed.pop()
    # only when the test body returned: a test that raised never reached its with lines
    for context in contexts:
        context.warn_if_unchecked()
    return result


_LIMIT = 40


def compare(actual: Any, expected: Any) -> tuple[Callable[[Any], str], list[str]]:
    """A repr for the headline's values, and pytest's explanation of `assert actual == expected`.

    Only values too long to read inline are explained; the headline then shortens them at
    every verbosity, since the explanation carries the detail. Outside pytest: `repr`, no lines.
    """
    if not _configs or all(len(repr(v)) <= _LIMIT for v in (actual, expected)):
        return repr, []
    config = _configs[-1]
    try:
        results = config.hook.pytest_assertrepr_compare(
            config=config, op="==", left=actual, right=expected
        )
    except Exception:  # noqa: BLE001 - a broken explanation must not hide the failure
        return repr, []
    for lines in results:
        if lines:
            # line 0 stands in for `left == right`, which the headline already says;
            # pytest escapes embedded newlines the same way
            explanation = [line.replace("\n", "\\n") for line in list(lines)[1:]]
            while explanation and not explanation[0].strip():
                explanation.pop(0)
            if explanation:
                return short_repr, explanation
    return repr, []


def short_repr(value: Any) -> str:
    """`repr`, eliding the middle of long values."""
    # mirrors pytest's saferepr: elide the middle, so both ends stay visible
    text = repr(value)
    if len(text) <= _LIMIT:
        return text
    keep = (_LIMIT - 3) // 2
    return f"{text[:keep]}...{text[-keep:]}"
