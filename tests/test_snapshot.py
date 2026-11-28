import enum
import threading
import types
import warnings

import pytest

from pytest_changes import ChangeAssertionError, ChangeWarning, changes, unchanged


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


class Account:
    def __init__(self, balance=100):
        self.balance = balance


class Users:
    """An ORM-style store: every find() loads a fresh object."""

    def find(self, id):
        return Account()


def hint(type_name):
    return (
        f"couldn't fully copy {type_name}, so the comparison may not reflect its contents: "
        "write a getter for the state you mean"
    )


class Color(enum.Enum):
    RED = 1


class TestIdentityEquality:
    def test_unchanged_warns_that_attribute_changes_are_invisible(self):
        acct = Account()
        with pytest.warns(ChangeWarning) as record, unchanged(lambda: acct):
            acct.balance = 999
        assert [str(w.message) for w in record] == [f"acct: {hint('Account')}"]
        assert record[0].filename == __file__

    def test_unchanged_warns_for_a_container(self):
        accounts = [Account()]
        with pytest.warns(ChangeWarning) as record, unchanged(lambda: accounts):
            accounts[0].balance = 999
        assert [str(w.message) for w in record] == [f"accounts: {hint('list')}"]

    def test_warns_when_only_a_shallow_copy_works(self):
        state = {"lock": threading.Lock(), "items": []}
        with pytest.warns(ChangeWarning) as record, unchanged(lambda: state):
            state["items"].append("x")
        assert [str(w.message) for w in record] == [f"state: {hint('dict')}"]

    def test_changes_failure_says_so(self):
        obj = Plain()
        with pytest.raises(ChangeAssertionError) as e, changes(lambda: obj):
            obj.status = "active"
        assert str(e.value).splitlines()[1] == f"  {hint('Plain')}"

    def test_fresh_object_warns_on_changes(self):
        db = Users()
        with pytest.warns(ChangeWarning) as record, changes(lambda: db.find(1)):
            pass
        assert [str(w.message) for w in record] == [f"db.find(1): {hint('Account')}"]

    def test_user_label_is_only_a_prefix(self):
        obj = Plain()
        with pytest.warns(ChangeWarning) as record, unchanged(lambda: obj, label="the obj"):
            pass
        assert [str(w.message) for w in record] == [f"the obj: {hint('Plain')}"]

    @pytest.mark.parametrize(
        "value", [Color.RED, Plain, len, hint], ids=["enum", "class", "builtin", "function"]
    )
    def test_values_copied_as_themselves_are_silent(self, value):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with unchanged(lambda: value, label="value"):
                pass

    def test_constraints_are_silent(self):
        old, new = Plain(), Plain()
        box = {"value": old}
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with changes(lambda: box["value"], to=new, label="value"):
                box["value"] = new

    def test_vars_getter_sees_attribute_change(self):
        obj = Plain()
        obj.status = "pending"
        with changes(lambda: vars(obj), to={"status": "active"}, label="obj"):
            obj.status = "active"

    def test_nan_is_not_identity(self):
        nan = float("nan")
        with pytest.raises(ChangeAssertionError) as e, unchanged(lambda: nan):
            pass
        assert str(e.value) == "nan: expected no change, got nan → nan"


@pytest.mark.filterwarnings("ignore::pytest_changes.ChangeWarning")  # locks compare by identity
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
        assert c.delta == 1


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

    def test_to_value_is_blamed(self):
        box = [1, 2]
        with pytest.raises(TypeError) as e, changes(lambda: box, to=Array(1, 2, 3)):
            box = [1, 2, 3]
        assert str(e.value) == (
            "box: to= Array doesn't compare to a bool; "
            "pass a comparable to= value, such as a list or tuple"
        )

    def test_stacked_failures_stay_visible(self):
        box, other = {"a": [0]}, [1]
        with (
            pytest.raises(TypeError) as e,
            changes(lambda: box["a"], label="a"),
            unchanged(lambda: other, label="other"),
        ):
            box["a"] = Array(0)
            other.append(2)
        assert str(e.value) == AMBIGUOUS
        assert str(e.value.__cause__) == "other: expected no change, got [1] → [1, 2]"

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


class TestLiveViews:
    @pytest.mark.parametrize(
        ("getter", "kind"),
        [
            (lambda d: d.keys(), "dict_keys"),
            (lambda d: d.values(), "dict_values"),
            (lambda d: d.items(), "dict_items"),
            (lambda d: types.MappingProxyType(d), "mappingproxy"),
        ],
        ids=["keys", "values", "items", "mappingproxy"],
    )
    def test_refused_on_entry(self, getter, kind):
        d = {"a": 1}
        with pytest.raises(TypeError) as e, unchanged(lambda: getter(d), label="d"):
            d["b"] = 2
        assert str(e.value) == (
            f"d: {kind} is a live view, so it can't be compared before and after: "
            "return a copy from the getter, such as list(...) or dict(...)"
        )
