import threading

import pytest

from pytest_changes import ChangeAssertionError, changes, unchanged


class Cart:
    def __init__(self):
        self.items = []


class TestInPlaceMutation:
    def test_append_counts_as_a_change(self):
        cart = Cart()
        with changes(cart, "items"):
            cart.items.append("x")

    def test_append_fails_unchanged(self):
        cart = Cart()
        with pytest.raises(ChangeAssertionError) as e, unchanged(cart, "items"):
            cart.items.append("x")
        assert str(e.value) == "cart.items: expected no change, got [] → ['x']"


class Plain:
    """Compares by identity: a copy never equals the original."""


class TestIdentityEquality:
    def test_object_left_alone_is_unchanged(self):
        obj = Plain()
        with unchanged(lambda: obj, label="obj"):
            pass

    def test_object_left_alone_fails_changes(self):
        obj = Plain()
        with pytest.raises(ChangeAssertionError), changes(lambda: obj, label="obj"):
            pass

    def test_container_left_alone_is_unchanged(self):
        items = [Plain()]
        with unchanged(lambda: items, label="items"):
            pass

    def test_container_left_alone_fails_changes(self):
        items = {"a": Plain()}
        with pytest.raises(ChangeAssertionError) as e, changes(lambda: items, label="items"):
            pass
        assert str(e.value).startswith("items: expected to change, stayed {'a': <")

    def test_attribute_change_is_not_a_change(self):
        obj = Plain()
        with pytest.raises(ChangeAssertionError), changes(lambda: obj, label="obj"):
            obj.status = "active"

    def test_vars_getter_sees_attribute_change(self):
        obj = Plain()
        obj.status = "pending"
        with changes(lambda: vars(obj), to={"status": "active"}, label="obj"):
            obj.status = "active"

    def test_container_mutated_in_place_counts_as_a_change(self):
        items = [Plain()]
        with changes(lambda: items, label="items"):
            items.append(Plain())


class TestUncopyable:
    def test_lock(self):
        lock = threading.Lock()
        with unchanged(lambda: lock, label="lock"):
            pass

    def test_generator_is_not_consumed(self):
        gen = (x for x in [1, 2])
        with unchanged(lambda: gen, label="gen"):
            pass
        assert list(gen) == [1, 2]


class TestInspect:
    def test_before_is_the_snapshot_and_after_the_live_value(self):
        cart = Cart()
        with changes(cart, "items") as c:
            cart.items.append("x")
        assert c.before == []
        assert c.after is cart.items

    def test_delta_of_a_set_mutated_in_place(self):
        tags = {"a"}
        with changes(lambda: tags, label="tags") as c:
            tags.add("b")
        assert c.delta == {"b"}


class Truthless:
    def __bool__(self):
        raise ValueError("The truth value of an array with more than one element is ambiguous")


class Array:
    """Like a numpy array: comparisons return an object with no truth value."""

    def __init__(self, *values):
        self.values = list(values)

    def __eq__(self, other):
        return Truthless()

    def __ne__(self, other):
        return Truthless()

    __hash__ = None


AMBIGUOUS = (
    "a: Array doesn't compare to a bool; "
    "return a comparable value from the getter, such as a list or tuple"
)


class TestComparisonWithoutTruth:
    def test_changes(self):
        a = Array(0, 0)
        with pytest.raises(TypeError) as e, changes(lambda: a):
            a.values[0] = 1
        assert str(e.value) == AMBIGUOUS
        assert e.value.__suppress_context__

    def test_unchanged(self):
        a = Array(0, 0)
        with pytest.raises(TypeError) as e, unchanged(lambda: a):
            pass
        assert str(e.value) == AMBIGUOUS

    def test_to(self):
        a = Array(0, 0)
        with pytest.raises(TypeError) as e, changes(lambda: a, to=[1, 0]):
            a = Array(1, 0)
        assert str(e.value) == AMBIGUOUS

    def test_uncopyable_value_is_not_masked(self):
        class Uncopyable(Array):
            def __deepcopy__(self, memo):
                raise TypeError("no deepcopy")

            def __copy__(self):
                raise TypeError("no copy")

        a = Uncopyable(0)
        with pytest.raises(TypeError) as e, changes(lambda: a, label="a"):
            a.values[0] = 1
        assert str(e.value) == AMBIGUOUS.replace("Array", "Uncopyable")
