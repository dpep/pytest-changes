"""Labels for change expectations, read from the caller's source where possible."""

from __future__ import annotations

import ast
import itertools
import linecache
import os
import sys
from types import CodeType, FrameType
from typing import Any

_PACKAGE = __name__.rpartition(".")[0]

# filename -> (calls keyed by end position, lambdas keyed by first line), None if unparseable
_Index = tuple[dict[tuple[int, int], ast.Call], dict[int, list[ast.Lambda]]]
_indexes: dict[str, _Index | None] = {}


class Pending:
    """What naming the expression needs, captured cheaply at the call; resolved on demand."""

    def __init__(self, getter: Any, attr: str | None):
        self.getter = getter
        self.attr = attr
        # a lambda names itself; anything else needs the caller's call site
        self.site = None if _is_lambda(getter, attr) else _call_site()

    def resolve(self) -> str:
        return label(self.getter, self.attr, self.site)


# the caller's code, instruction offset and globals: enough to find the call, without the frame
_Site = tuple[CodeType, int, dict[str, Any]]


def label(getter: Any, attr: str | None, site: _Site | None) -> str:
    """Name the expression the user passed; never raises."""
    try:
        text = _from_source(getter, attr, site)
    except Exception:  # noqa: BLE001 - labelling must never break a test
        text = None
    if text is not None:
        return text
    try:
        return _fallback(getter, attr)
    except Exception:  # noqa: BLE001 - e.g. a getter whose __repr__ raises
        return f"<{type(getter).__name__}>"


def _from_source(getter: Any, attr: str | None, site: _Site | None) -> str | None:
    if _is_lambda(getter, attr):
        return _lambda_body(getter.__code__, getter.__globals__)

    call = _find_call(site) if site is not None else None
    # same call shape as changes(obj, "attr") / changes(getter), else it's someone else's call
    if call is None or len(call.args) != (1 if attr is None else 2):
        return None
    first = call.args[0]
    if isinstance(first, ast.Starred):
        return None
    if attr is None:
        return f"{ast.unparse(first)}()"
    second = call.args[1]
    if isinstance(second, ast.Constant) and second.value != attr:
        return None
    return f"{ast.unparse(first)}.{attr}"


def _is_lambda(getter: Any, attr: str | None) -> bool:
    return attr is None and getattr(getter, "__name__", None) == "<lambda>"


def _call_site() -> _Site | None:
    try:
        frame: FrameType | None = sys._getframe(1)
    except Exception:  # noqa: BLE001 - no frame introspection (non-CPython); fall back
        return None
    while frame is not None and _in_package(frame.f_globals.get("__name__")):
        frame = frame.f_back
    if frame is None:
        return None
    return frame.f_code, frame.f_lasti, frame.f_globals


def _find_call(site: _Site) -> ast.Call | None:
    code, lasti, module_globals = site
    pos = next(itertools.islice(code.co_positions(), lasti // 2, None), None)
    if pos is None or None in pos:
        return None
    index = _index(code.co_filename, module_globals)
    # match on the end: a multi-line method call's start is moved to the attribute name
    return index[0].get((pos[1], pos[3])) if index else None


def _lambda_body(code: CodeType, module_globals: dict[str, Any]) -> str | None:
    # zero-width positions are bookkeeping (RESUME etc.), not body expressions
    spans = [
        ((line, col), (end_line, end_col))
        for line, end_line, col, end_col in code.co_positions()
        if None not in (line, end_line, col, end_col) and (line, col) != (end_line, end_col)
    ]
    index = _index(code.co_filename, module_globals)
    if not spans or not index:
        return None
    start = min(s for s, _ in spans)
    end = max(e for _, e in spans)
    candidates = [
        node.body
        for node in index[1].get(code.co_firstlineno, [])
        if (node.body.lineno, node.body.col_offset) <= start
        and end <= (node.body.end_lineno, node.body.end_col_offset)
    ]
    if not candidates:
        return None
    # innermost wins when lambdas nest
    body = max(candidates, key=lambda b: (b.lineno, b.col_offset))
    return ast.unparse(body)


def _index(filename: str, module_globals: dict[str, Any]) -> _Index | None:
    if filename in _indexes:
        return _indexes[filename]
    lines = linecache.getlines(filename, module_globals)
    if not lines:
        return None  # no source (exec, compile); not cached in case it's registered later
    try:
        index = _build("".join(lines))
    except Exception:  # noqa: BLE001 - unparseable source (stale, syntax error, too deep)
        index = None
    _indexes[filename] = index
    return index


def _build(source: str) -> _Index:
    calls: dict[tuple[int, int], ast.Call] = {}
    lambdas: dict[int, list[ast.Lambda]] = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            calls[(node.end_lineno, node.end_col_offset)] = node
        elif isinstance(node, ast.Lambda):
            lambdas.setdefault(node.lineno, []).append(node)
    return calls, lambdas


def _in_package(module: object) -> bool:
    return isinstance(module, str) and (module == _PACKAGE or module.startswith(_PACKAGE + "."))


def _fallback(getter: Any, attr: str | None) -> str:
    if attr is not None:
        return f"<{type(getter).__name__}>.{attr}"
    code = getattr(getter, "__code__", None)
    if code is None:
        return repr(getter)
    name = "lambda" if getter.__name__ == "<lambda>" else getter.__qualname__.rsplit(".", 1)[-1]
    return f"<{name} at {os.path.basename(code.co_filename)}:{code.co_firstlineno}>"
