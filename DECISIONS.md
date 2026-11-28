# Decisions

Roads not taken, and why. The code shows what was chosen; this records what was
considered and turned down, so a rejected idea comes back with new evidence rather
than fresh confidence. Only tempting paths belong here. What changed lives in
`CHANGELOG.md`; the rules live in `CLAUDE.md`.

---

## No `from_=`

**Considered:** `changes(..., from_=1, to=2)`, mirroring RSpec's `from(1).to(2)`.

**Rejected because** the start value is already readable before the block: `assert
cart.total == 1` says it plainly, and one fewer keyword keeps `to`/`by` the whole
vocabulary.

*Reverses if:* users repeatedly write the pre-assert by hand and ask for it.

## No `snapshot=` parameter

**Considered:** `changes(user, snapshot=vars)` to choose how the value is copied.

**Rejected because** a getter already does it (`lambda: vars(user)`), and `snapshot=vars`
would false-pass when the snapshot function misses the state that changed.

## The check is skipped when the block raises

**Considered:** checking expectations even when the block raises, so `unchanged` could
guard an error path from inside `pytest.raises`.

**Rejected because** it was built and reverted. `pytest.raises(Exception)` swallows a
`ChangeAssertionError` (it is an `Exception`), `SystemExit` paths misbehave, a getter error
masks the user's exception, and `-W error` turns hints into the wrong failure. Instead the
check is skipped, an after-test `ChangeWarning` names it, and the README teaches `with
unchanged(...), pytest.raises(X):`.

*Reverses if:* a design survives all four of those.

## Δ counts items only for built-in collections

**Considered:** counting length for anything sized, or falling back to `len` when `-`
fails.

**Rejected because** length-first broke `Counter`, vectors and money types, and the `len`
fallback let strings count characters: a counter stored as `"9"` → `"14"` passed `by=1`.
Lists, tuples, sets and dicts count items; a `Counter` uses `Counter.subtract` (its `-`
drops counts at or below zero); everything else is `after - before` or a `TypeError`.

*Reverses if:* a sized type shows up where counting is unambiguous and subtraction can't
express it.

## No `by_at_least` / `by_at_most`

**Considered:** bounded deltas as their own keywords.

**Rejected because** `by=range(a, b)` covers bounded cases with Python's own semantics,
and `assert c.delta >= 1` covers open ones without new vocabulary.

## `by=range` needs integer deltas

**Considered:** interval semantics for float or `Decimal` deltas.

**Rejected because** `range` is integer-only in Python, and a message like "Δ in 1..2, got
Δ +1.5" reads as a contradiction. Non-integer deltas raise `TypeError` pointing at
`c.delta`.

## No `by=0` guard

**Considered:** refusing `by=0` as a likely mistake for `unchanged`.

**Rejected because** the guard needed three exceptions (`pytest.approx(0, abs=1)`,
`mock.ANY`, numbers only), and RSpec's `by(0)` passes on no change too.

## Call-site labels stay, resolved lazily

**Considered:** dropping AST-derived labels for simpler `<lambda>` names.

**Rejected because** testers valued them, and they disambiguate stacked expectations. They
resolve only on failure, so a passing block never reads source.

## Unchecked contexts warn after the test, not in `__del__`

**Considered:** warning from `__del__` when a context was never entered.

**Rejected because** garbage collection timing decides which test, if any, sees the
warning. The plugin checks when each test returns, attributes the warning to the
construction line, and stays quiet when the test failed.

## Contexts are reusable, one block at a time

**Considered:** single-use contexts.

**Rejected because** `parametrize` and reruns reuse the same object. Only re-entering an
active context is refused, and an earlier unchecked block is still reported.

## The error keeps its real module

**Considered:** setting `ChangeAssertionError.__module__ = "builtins"` so tracebacks read
`AssertionError`.

**Deferred because** it lies about the import path. Revisit if pytest's short-summary
truncation makes `pytest_changes.ChangeAssertionError` a real problem.

---

## Deferred gaps

Known, minor, and not worth a rule with an exception yet.

- Under `-W error`, a passing middle context's copy warning breaks the stacked merge;
  the inner failure survives as the warning's `__context__`.
- `c.after` after a getter error says it is "read when the with block exits".
- In `with a, b:` where `b`'s getter raises, `a`'s warning blames the block.
- Hypothesis `assume()` triggers false "never entered" warnings.
- A context made in a module-scoped fixture warns in whichever test is running.
- A failing unittest `subTest` still warns.
- `range(2, 3)` reads "Δ in 2..2"; `Counter` failure messages show zero entries.
