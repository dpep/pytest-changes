import warnings

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
    assert str(e.value) == "audit.value: expected no change, got 4 → 5"


class InsufficientFunds(Exception):
    pass


def withdraw_buggy(acct, amount, error=None):
    acct.value -= amount
    raise error or InsufficientFunds()


# the block raises inside pytest.raises, so the plugin warns when the test returns
UNCHECKED = pytest.mark.filterwarnings("ignore::pytest_changes.ChangeWarning")


class TestBlockRaises:
    @UNCHECKED
    def test_skips_the_check(self):
        acct = Counter(50)
        error = InsufficientFunds()
        with pytest.raises(InsufficientFunds) as e, unchanged(acct, "value"):
            withdraw_buggy(acct, 100, error)
        assert e.value is error
        assert e.value.__context__ is None

    def test_expectation_outside_pytest_raises_catches_mutate_then_raise(self):
        acct = Counter(50)
        with pytest.raises(ChangeAssertionError) as e:  # noqa: SIM117
            with unchanged(acct, "value"), pytest.raises(InsufficientFunds):
                withdraw_buggy(acct, 100)
        assert str(e.value) == "acct.value: expected no change, got 50 → -50"

    @UNCHECKED
    @pytest.mark.parametrize(
        "stop",
        [
            ValueError,
            SystemExit,
            KeyboardInterrupt,
            lambda: pytest.skip("no"),
            lambda: pytest.fail(),
        ],
    )
    def test_leaving_the_block_never_warns(self, stop):
        acct = Counter(50)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with pytest.raises(BaseException) as e, unchanged(acct, "value"):
                acct.value = 0
                if isinstance(stop, type):
                    raise stop
                stop()
        assert not isinstance(e.value, Warning)
