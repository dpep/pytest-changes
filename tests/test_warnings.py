import inspect
import warnings

import pytest

from pytest_changes import ChangeWarning, changes, unchanged


class Counter:
    def __init__(self, value=0):
        self.value = value


class TestNeverEntered:
    def test_warns_at_the_call(self):
        counter = Counter()
        line = inspect.currentframe().f_lineno + 2
        with pytest.warns(ChangeWarning) as record:
            changes(counter, "value", by=999)
        assert str(record[0].message) == (
            "changes() was never entered, so it asserts nothing: use it in a with statement"
        )
        assert (record[0].filename, record[0].lineno) == (__file__, line)

    def test_unchanged(self):
        with pytest.warns(ChangeWarning, match=r"^unchanged\(\) was never entered"):
            unchanged(Counter(), "value")

    def test_entered_is_silent(self):
        counter = Counter()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            context = changes(counter, "value")
            with context:
                counter.value += 1
            del context

    def test_failed_construction_is_silent(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with pytest.raises(TypeError):
                changes(Counter(), "value", to=1, by=1)

    def test_is_a_runtime_warning(self):
        assert issubclass(ChangeWarning, RuntimeWarning)

    def test_reported_by_pytest(self, pytester):
        pytester.makepyfile(
            """
            from pytest_changes import changes

            class Cart:
                total = 0

            def test_it():
                changes(Cart(), "total", by=999)
            """
        )
        result = pytester.runpytest_subprocess()
        result.assert_outcomes(passed=1, warnings=1)
        result.stdout.fnmatch_lines(
            ["*test_reported_by_pytest.py:7: ChangeWarning: changes() was*"]
        )

        result = pytester.runpytest_subprocess("-W", "error")
        result.assert_outcomes(failed=1)
        result.stdout.fnmatch_lines(["E *ChangeWarning: changes() was never entered*"])
