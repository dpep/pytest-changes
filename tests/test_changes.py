import pytest

from pytest_changes import ChangeAssertionError, changes


class Counter:
    def __init__(self, value=0):
        self.value = value


@pytest.fixture
def counter():
    return Counter()


def message(excinfo):
    return str(excinfo.value)


class TestAnyChange:
    def test_passes_when_value_changes(self, counter):
        with changes(counter, "value"):
            counter.value += 1

    def test_fails_when_value_stays(self, counter):
        with pytest.raises(ChangeAssertionError) as e, changes(counter, "value"):
            pass
        assert message(e) == "counter.value: expected to change, stayed 0"


class TestTo:
    def test_passes(self, counter):
        with changes(counter, "value", to=20):
            counter.value = 20

    def test_wrong_end(self, counter):
        with pytest.raises(ChangeAssertionError) as e, changes(counter, "value", to=20):
            counter.value = 15
        assert message(e) == "counter.value: expected → 20, got 0 → 15 (Δ +15)"

    def test_strings(self):
        user = Counter("pending")
        with pytest.raises(ChangeAssertionError) as e, changes(user, "value", to="active"):
            user.value = "banned"
        assert message(e) == "user.value: expected → 'active', got 'pending' → 'banned'"

    def test_requires_a_change(self):
        user = Counter("active")
        with pytest.raises(ChangeAssertionError) as e, changes(user, "value", to="active"):
            pass
        assert message(e) == "user.value: expected → 'active', stayed 'active'"


class TestBy:
    def test_passes(self, counter):
        with changes(counter, "value", by=20):
            counter.value += 20

    def test_fails(self, counter):
        with pytest.raises(ChangeAssertionError) as e, changes(counter, "value", by=20):
            counter.value += 15
        assert message(e) == "counter.value: expected Δ +20, got Δ +15 (0 → 15)"

    def test_negative(self, counter):
        with changes(counter, "value", by=-1):
            counter.value -= 1

    def test_zero_passes_without_change(self, counter):
        with changes(counter, "value", by=0):
            pass

    def test_values_that_cannot_subtract(self):
        user = Counter("a")
        with (
            pytest.raises(TypeError, match=r"user\.value: by= needs after - before.*str"),
            changes(user, "value", by=1),
        ):
            user.value = "b"

    def test_matcher(self):
        total = Counter(0.1)
        with changes(total, "value", by=pytest.approx(0.2)):
            total.value += 0.2


class TestGetter:
    def test_lambda(self, counter):
        with changes(lambda: counter.value, by=1):
            counter.value += 1

    def test_lambda_label(self, counter):
        with pytest.raises(ChangeAssertionError) as e, changes(lambda: counter.value):
            pass
        assert message(e) == "counter.value: expected to change, stayed 0"

    def test_function_label(self, counter):
        def total():
            return counter.value

        with pytest.raises(ChangeAssertionError) as e, changes(total):
            pass
        assert message(e) == "total(): expected to change, stayed 0"

    def test_label_argument(self, counter):
        with (
            pytest.raises(ChangeAssertionError) as e,
            changes(lambda: counter.value, label="counter"),
        ):
            pass
        assert message(e) == "counter: expected to change, stayed 0"

    def test_callable_object_with_attr_uses_attr(self):
        class Callable:
            value = 0

            def __call__(self):
                raise AssertionError("not the getter")

        obj = Callable()
        with changes(obj, "value", by=1):
            obj.value += 1

    def test_not_callable(self, counter):
        with pytest.raises(TypeError, match="callable"):
            changes(counter)

    def test_getter_error_before_the_block_names_the_label(self):
        with pytest.raises(ZeroDivisionError) as e, changes(lambda: 1 / 0, label="ratio"):
            pass
        assert "ratio" in e.value.__notes__[0]
        assert "before the block" in e.value.__notes__[0]

    def test_getter_error_after_the_block(self):
        state = {"ok": True}
        with pytest.raises(KeyError) as e, changes(lambda: state["ok"], label="state"):
            del state["ok"]
        assert "after the block completed" in e.value.__notes__[0]


class TestInspect:
    def test_exposes_before_after_and_delta(self, counter):
        with changes(counter, "value") as c:
            counter.value = 3
        assert (c.before, c.after, c.delta) == (0, 3, 3)
        assert c.label == "counter.value"


class TestBlockErrors:
    def test_other_exceptions_pass_through_unchecked(self, counter):
        with pytest.raises(ValueError), changes(counter, "value", by=1):
            raise ValueError

    def test_plain_assertion_errors_pass_through(self, counter):
        with pytest.raises(AssertionError) as e, changes(counter, "value", by=1):
            raise AssertionError("mine")
        assert type(e.value) is AssertionError


class TestInvalidCombos:
    def test_to_and_by(self, counter):
        with pytest.raises(TypeError, match="cannot combine to and by"):
            changes(counter, "value", to=1, by=1)
