import pytest

from pytest_changes import ChangeAssertionError, unchanged


class Counter:
    def __init__(self, value=0):
        self.value = value


def test_passes_when_value_stays():
    counter = Counter(4)
    with unchanged(counter, "value"):
        pass


def test_fails_when_value_changes():
    audit = Counter(4)
    with pytest.raises(ChangeAssertionError) as e, unchanged(audit, "value"):
        audit.value += 1
    assert str(e.value) == "audit.value: expected no change, got 4 → 5 (Δ +1)"


def test_omits_delta_when_values_cannot_subtract():
    user = Counter("a")
    with pytest.raises(ChangeAssertionError) as e, unchanged(lambda: user.value, label="user"):
        user.value = "b"
    assert str(e.value) == "user: expected no change, got 'a' → 'b'"


class InsufficientFunds(Exception):
    pass


def withdraw_buggy(acct, amount):
    acct.value -= amount
    raise InsufficientFunds


class TestBlockRaises:
    def test_change_fails_chained_from_the_block_error(self):
        acct = Counter(50)
        with (
            pytest.raises(ChangeAssertionError) as e,
            pytest.raises(InsufficientFunds),
            unchanged(acct, "value"),
        ):
            withdraw_buggy(acct, 100)
        assert str(e.value) == "acct.value: expected no change, got 50 → -50 (Δ -100)"
        assert isinstance(e.value.__cause__, InsufficientFunds)

    def test_no_change_lets_the_error_through_untouched(self):
        acct = Counter(50)
        error = InsufficientFunds()
        with pytest.raises(InsufficientFunds) as e, unchanged(acct, "value"):
            raise error
        assert e.value is error
        assert e.value.__context__ is None

    def test_control_flow_exceptions_skip_the_check(self):
        acct = Counter(50)
        with pytest.raises(pytest.skip.Exception), unchanged(acct, "value"):
            acct.value = 0
            pytest.skip("not today")

    def test_getter_error_after_the_block_raised(self):
        state = {"ok": True}
        with pytest.raises(KeyError) as e, unchanged(lambda: state["ok"], label="state"):
            del state["ok"]
            raise InsufficientFunds
        assert "after the block raised" in e.value.__notes__[0]
        assert isinstance(e.value.__context__, InsufficientFunds)
