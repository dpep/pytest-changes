import warnings

import pytest

from pytest_changes import ChangeAssertionError, ChangeWarning, unchanged


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


def warning(label, error, make="unchanged"):
    return (
        f"{label}: not checked because the block raised {error}: put the expectation "
        f"outside pytest.raises: with {make}(...), pytest.raises({error}):"
    )


class TestBlockRaises:
    def test_skips_the_check_and_warns(self):
        acct = Counter(50)
        error = InsufficientFunds()
        with (
            pytest.warns(ChangeWarning) as record,
            pytest.raises(InsufficientFunds) as e,
            unchanged(acct, "value"),
        ):
            withdraw_buggy(acct, 100, error)
        assert e.value is error
        assert e.value.__context__ is None
        assert [str(w.message) for w in record] == [warning("acct.value", "InsufficientFunds")]
        assert record[0].filename == __file__

    def test_expectation_outside_pytest_raises_catches_mutate_then_raise(self):
        acct = Counter(50)
        with pytest.raises(ChangeAssertionError) as e:  # noqa: SIM117
            with unchanged(acct, "value"), pytest.raises(InsufficientFunds):
                withdraw_buggy(acct, 100)
        assert str(e.value) == "acct.value: expected no change, got 50 → -50"

    def test_system_exit_warns(self):
        acct = Counter(50)
        with pytest.warns(ChangeWarning) as record, pytest.raises(SystemExit):  # noqa: SIM117
            with unchanged(acct, "value"):
                raise SystemExit(2)
        assert [str(w.message) for w in record] == [warning("acct.value", "SystemExit")]

    @pytest.mark.parametrize(
        "stop", [lambda: pytest.skip("not today"), lambda: pytest.fail("no"), KeyboardInterrupt]
    )
    def test_test_outcomes_and_interrupts_are_silent(self, stop):
        acct = Counter(50)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with pytest.raises(BaseException) as e, unchanged(acct, "value"):
                acct.value = 0
                if isinstance(stop, type):
                    raise stop
                stop()
        assert not isinstance(e.value, Exception | SystemExit)

    def test_warning_as_error_keeps_the_block_error_visible(self, pytester):
        pytester.makepyfile(
            """
            from pytest_changes import unchanged

            def test_it():
                box = [1]
                with unchanged(lambda: box):
                    raise ValueError("the real problem")
            """
        )
        result = pytester.runpytest_subprocess("-W", "error::pytest_changes.ChangeWarning")
        result.assert_outcomes(failed=1)
        result.stdout.fnmatch_lines(
            [
                "*ValueError: the real problem",
                "*During handling of the above exception, another exception occurred*",
                "E *ChangeWarning: box: not checked because the block raised ValueError*",
            ]
        )
