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


WHERE_BUILT = """
    import threading
    import unittest

    import pytest
    from pytest_changes import changes

    USE = {use}

    class Cart:
        total = 0

    def expect(cart):
        return changes(cart, "total")

    @pytest.fixture
    def expectation():
        return expect(Cart())

    def test_fixture(expectation):
        if USE:
            with expectation:
                Cart.total += 1

    def test_helper():
        expectation = expect(Cart())
        if USE:
            with expectation:
                Cart.total += 1

    class TestClass:
        def test_method(self):
            expectation = expect(Cart())
            if USE:
                with expectation:
                    Cart.total += 1

    class TestCase(unittest.TestCase):
        def setUp(self):
            self.expectation = expect(Cart())

        def test_unittest(self):
            if USE:
                with self.expectation:
                    Cart.total += 1

        def test_unittest_failure_stays_quiet(self):
            with self.expectation:
                raise ValueError

    def test_thread():
        made = []
        thread = threading.Thread(target=lambda: made.append(expect(Cart())))
        thread.start()
        thread.join()
        if USE:
            with made[0]:
                Cart.total += 1

    @pytest.mark.parametrize("n", [1, 2])
    def test_parametrize(n):
        expectation = expect(Cart())
        if USE:
            with expectation:
                Cart.total += n
"""


class TestWhereBuilt:
    def test_forgotten_contexts_warn_wherever_they_are_built(self, pytester):
        pytester.makepyfile(WHERE_BUILT.format(use=False))
        result = pytester.runpytest_subprocess("-W", "error::pytest_changes.ChangeWarning")
        result.assert_outcomes(failed=8)
        assert result.stdout.str().count("ChangeWarning: changes() was never entered") == 7

    def test_used_contexts_stay_quiet(self, pytester):
        pytester.makepyfile(WHERE_BUILT.format(use=True))
        result = pytester.runpytest_subprocess("-W", "error::pytest_changes.ChangeWarning")
        result.assert_outcomes(passed=7, failed=1)
        assert "ChangeWarning" not in result.stdout.str()
