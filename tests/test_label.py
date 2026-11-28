import ast
import importlib.util
import itertools
import weakref

import pytest

from pytest_changes import ChangeAssertionError, _label, changes, unchanged

# these tests build contexts without entering them, just to read their labels
pytestmark = pytest.mark.filterwarnings("ignore::pytest_changes.ChangeWarning")


class Cart:
    def __init__(self):
        self.total = 0
        self.items = []

    def count(self):
        return len(self.items)


class Audit:
    def __init__(self):
        self.count = 4


CART = Cart()


def cart_total():
    return CART.total


def watching(getter):
    def wrap(fn):
        fn.getter = getter
        return fn

    return wrap


@watching(lambda: CART.total + 1)
def decorated():
    pass


def with_default(getter=lambda: len(CART.items)):
    return changes(getter)


_modules = itertools.count()


def load(tmp_path, source):
    path = tmp_path / f"labelled_{next(_modules)}.py"
    path.write_text(source)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


class TestObjectAttr:
    def setup_method(self):
        self.cart = Cart()

    def test_uses_source_of_the_object(self):
        assert changes(self.cart, "total").label == "self.cart.total"

    def test_multi_line_call(self):
        context = changes(
            self.cart,
            "total",
            by=20,
        )
        assert context.label == "self.cart.total"

    def test_attr_from_a_variable(self):
        attr = "total"
        assert changes(self.cart, attr).label == "self.cart.total"

    def test_stacked_with_block(self):
        cart, audit = Cart(), Audit()
        with (
            pytest.raises(ChangeAssertionError) as e,
            changes(cart, "total", by=20),
            changes(lambda: len(cart.items), by=1),
            unchanged(audit, "count"),
        ):
            cart.total += 15
            cart.items.append("x")
            audit.count += 1
        assert str(e.value) == (
            "2 change expectations failed\n"
            "  ✗ cart.total   expected Δ +20, got Δ +15 (0 → 15)\n"
            "  ✗ audit.count  expected no change, got 4 → 5 (Δ +1)"
        )


class TestLambda:
    def test_body_as_written(self):
        cart = Cart()
        assert changes(lambda: len(cart.items)).label == "len(cart.items)"

    def test_two_on_one_line(self):
        a, b = changes(lambda: CART.total), changes(lambda: len(CART.items))
        assert (a.label, b.label) == ("CART.total", "len(CART.items)")

    def test_nested(self):
        context = changes(lambda: sorted(CART.items, key=lambda i: -i))
        assert context.label == "sorted(CART.items, key=lambda i: -i)"

    def test_multi_line_body(self):
        context = changes(
            lambda: (
                CART.total
                + len(CART.items)
                + max(CART.total, len(CART.items), CART.count())
                + max(CART.total, len(CART.items), CART.count())
            )
        )
        assert context.label == (
            "CART.total + len(CART.items)"
            " + max(CART.total, len(CART.items), CART.count())"
            " + max(CART.total, len(CART.items), CART.count())"
        )

    def test_in_a_decorator(self):
        assert changes(decorated.getter).label == "CART.total + 1"

    def test_as_a_default_argument(self):
        assert with_default().label == "len(CART.items)"


class TestNamedGetter:
    def test_function_defined_elsewhere(self):
        assert changes(cart_total).label == "cart_total()"

    def test_bound_method(self):
        assert changes(CART.count).label == "CART.count()"

    def test_label_argument_wins(self):
        assert changes(cart_total, label="total").label == "total"


class TestFallback:
    def test_exec_without_source(self):
        namespace = {"changes": changes, "cart": Cart()}
        code = compile(
            "a = changes(lambda: cart.total)\nb = changes(cart, 'total')\nc = changes(cart.count)",
            "<string>",
            "exec",
        )
        exec(code, namespace)  # noqa: S102
        assert namespace["a"].label == "<lambda at <string>:1>"
        assert namespace["b"].label == "<Cart>.total"
        assert namespace["c"].label == "<count at test_label.py:19>"
        # the lambda's globals are this dict; break the cycle so its contexts die in this test
        namespace.clear()

    def test_call_shape_mismatch(self):
        # partial makes the call site a different call
        from functools import partial

        assert partial(changes, CART)("total").label == "<Cart>.total"

    def test_stale_source(self, tmp_path):
        module, path = load(
            tmp_path,
            "from pytest_changes import changes\n"
            "def build(cart):\n"
            "    return changes(cart, 'total'), changes(lambda: cart.total)\n",
        )
        path.write_text("\n\nx = (\n  1)\ny = lambda: 2\n")
        labels = [c.label for c in module.build(Cart())]
        assert all(isinstance(label, str) for label in labels)

    def test_unparseable_source(self, tmp_path):
        module, path = load(
            tmp_path,
            "from pytest_changes import changes\n"
            "def build(cart):\n"
            "    return changes(cart, 'total'), changes(lambda: cart.total)\n",
        )
        path.write_text("def (:\n")
        labels = [c.label for c in module.build(Cart())]
        assert labels[0] == "<Cart>.total"
        assert labels[1].startswith("<lambda at labelled_")

    def test_labeller_errors_fall_back(self, monkeypatch):
        def boom(*args):
            raise RuntimeError

        monkeypatch.setattr(_label, "_from_source", boom)
        assert changes(CART, "total").label == "<Cart>.total"

    def test_broken_repr_never_raises(self, monkeypatch):
        class Getter:
            def __call__(self):
                return 0

            def __repr__(self):
                raise RuntimeError

        monkeypatch.setattr(_label, "_from_source", lambda *args: None)
        assert changes(Getter()).label == "<Getter>"


class TestLazy:
    def test_passing_block_reads_no_source(self, monkeypatch):
        monkeypatch.setattr(_label, "_index", lambda *a: pytest.fail("read source"))
        cart = Cart()
        with changes(cart, "total", by=1), changes(lambda: cart.total), unchanged(cart.count):
            cart.total += 1

    def test_resolves_after_the_callers_frame_is_gone(self):
        def build():
            cart = Cart()
            return changes(cart, "total", by=1), changes(cart.count, by=1), cart

        total, count, cart = build()
        with pytest.raises(ChangeAssertionError) as e, total, count:
            cart.total += 2
        assert str(e.value) == (
            "2 change expectations failed\n"
            "  ✗ cart.total    expected Δ +1, got Δ +2 (0 → 2)\n"
            "  ✗ cart.count()  expected Δ +1, did not change (stayed 0)"
        )

    def test_holds_no_frame(self):
        def build():
            bystander = Cart()
            return changes(CART, "total"), weakref.ref(bystander)

        context, ref = build()
        assert ref() is None
        assert context.label == "CART.total"

    def test_getter_error_note(self):
        cart = Cart()
        with pytest.raises(AttributeError) as e, changes(cart, "missing"):
            pass
        assert e.value.__notes__ == ["raised by the getter for cart.missing before the block"]


def test_parses_each_file_once(tmp_path, monkeypatch):
    module, _ = load(
        tmp_path,
        "from pytest_changes import changes\n"
        "def build(cart):\n"
        "    return changes(cart, 'total'), changes(lambda: cart.total)\n",
    )
    calls = []
    parse = ast.parse
    monkeypatch.setattr(ast, "parse", lambda *a, **k: calls.append(1) or parse(*a, **k))
    labels = [c.label for _ in range(3) for c in module.build(Cart())]
    assert labels == ["cart.total", "cart.total"] * 3
    assert len(calls) == 1
