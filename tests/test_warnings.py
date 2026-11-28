from pytest_changes import ChangeWarning

UNCHECKED = """
    import pytest
    from pytest_changes import changes, unchanged

    class Cart:
        total = 0

    def test_never_entered():
        changes(Cart(), "total", by=999)

    def test_never_entered_with_a_lambda():
        cart = Cart()
        unchanged(lambda: cart.total, label="total")

    def test_block_raised_inside_pytest_raises():
        cart = Cart()
        with pytest.raises(ValueError), unchanged(lambda: cart.total):
            raise ValueError

    def test_entered():
        cart = Cart()
        context = changes(cart, "total")
        with context:
            cart.total += 1

    def test_failed_construction():
        with pytest.raises(TypeError):
            changes(Cart(), "total", to=1, by=1)

    def test_raised_before_the_with():
        changes(Cart(), "total")
        raise ValueError("the real failure")

    def test_raised_inside_the_block():
        with changes(Cart(), "total"):
            raise ValueError("the real failure")
"""


class TestUnchecked:
    def test_warns_at_the_call_after_the_test_returns(self, pytester):
        pytester.makepyfile(UNCHECKED)
        result = pytester.runpytest_subprocess()
        result.assert_outcomes(passed=5, failed=2, warnings=3)
        result.stdout.fnmatch_lines(
            [
                (
                    "*.py:8: ChangeWarning: changes() was never entered, so it asserts nothing: "
                    "use it in a with statement"
                ),
                "*.py:12: ChangeWarning: unchanged() was never entered*",
                (
                    "*.py:16: ChangeWarning: cart.total: wasn't checked because the block raised "
                    "ValueError: put the expectation outside pytest.raises: "
                    "with unchanged(...), pytest.raises(ValueError):"
                ),
            ]
        )

    def test_warning_as_error_fails_only_the_tests_that_returned(self, pytester):
        pytester.makepyfile(UNCHECKED)
        result = pytester.runpytest_subprocess("-W", "error::pytest_changes.ChangeWarning")
        result.assert_outcomes(passed=2, failed=5)
        result.stdout.fnmatch_lines(["E *ChangeWarning: changes() was never entered*"])
        result.stdout.fnmatch_lines(["E *ValueError: the real failure"] * 2)

    def test_is_a_runtime_warning(self):
        assert issubclass(ChangeWarning, RuntimeWarning)
