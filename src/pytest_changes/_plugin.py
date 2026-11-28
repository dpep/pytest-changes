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
    # pytest unconfigures even when another plugin's pytest_configure failed before ours ran
    if config in _configs:
        _configs.remove(config)


# contexts made or entered by each running test, from setup through the call; innermost
# (pytester) run last
_tracked: list[list[Any]] = []


def track(context: Any) -> bool:
    """Attribute `context` to the running test; True if it wasn't already."""
    if not _tracked or any(c is context for c in _tracked[-1]):
        return False
    _tracked[-1].append(context)
    return True


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> Any:
    _tracked.append([])
    return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Any:
    __tracebackhide__ = True
    result = yield
    # only when the test returned: a test that raised never reached its with lines.
    # unittest records failures on the item instead of raising them
    if not getattr(item, "_excinfo", None):
        for context in _tracked[-1]:
            context.warn_if_unchecked()
    return result


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item: pytest.Item) -> Any:
    # teardown runs whenever setup did, even when setup or the call failed
    _tracked.pop()
    return (yield)


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
