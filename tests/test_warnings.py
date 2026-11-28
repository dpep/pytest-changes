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
        # the E lines, since the short summary repeats messages untruncated under CI=true
        raised = [line for line in result.outlines if line.startswith("E ")]
        assert sum("ChangeWarning: changes() was never entered" in line for line in raised) == 7

    def test_used_contexts_stay_quiet(self, pytester):
        pytester.makepyfile(WHERE_BUILT.format(use=True))
        result = pytester.runpytest_subprocess("-W", "error::pytest_changes.ChangeWarning")
        result.assert_outcomes(passed=7, failed=1)
        assert "ChangeWarning" not in result.stdout.str()


GETTER_RAISED = """
    import pytest
    from pytest_changes import changes, unchanged

    def test_before():
        store = {}
        with pytest.raises(KeyError), unchanged(lambda: store["count"]):
            pass

    def test_after():
        store = {"count": 1}
        with pytest.raises(KeyError), changes(lambda: store["count"], by=1):
            del store["count"]

    def test_failing_stays_quiet():
        store = {}
        with unchanged(lambda: store["count"]):
            pass
"""


class TestGetterRaised:
    def test_warns_that_the_getter_raised(self, pytester):
        pytester.makepyfile(GETTER_RAISED)
        result = pytester.runpytest_subprocess()
        result.assert_outcomes(passed=2, failed=1, warnings=2)
        # [[] matches a literal [ in fnmatch
        result.stdout.fnmatch_lines(
            [
                (
                    "*.py:6: ChangeWarning: store[[]'count']: wasn't checked because the getter "
                    "raised KeyError before the block: make the getter return a value before "
                    "and after the block"
                ),
                (
                    "*.py:11: ChangeWarning: store[[]'count']: wasn't checked because the getter "
                    "raised KeyError after the block: make the getter return a value before "
                    "and after the block"
                ),
            ]
        )


MADE_AT_IMPORT = """
    import pytest
    from pytest_changes import changes, unchanged

    state = {"n": 0}
    EXPECTATIONS = [changes(lambda: state["n"]), unchanged(lambda: state["n"], label="same")]

    @pytest.mark.parametrize("ctx", EXPECTATIONS)
    def test_raised(ctx):
        with pytest.raises(ValueError), ctx:
            raise ValueError

    def test_checked_after_a_skip_in_another_test():
        with EXPECTATIONS[0]:
            state["n"] += 1

    @pytest.mark.parametrize("ctx", EXPECTATIONS)
    def test_never_entered(ctx):
        pass
"""


class TestMadeAtImport:
    def test_warns_in_the_test_that_entered_it(self, pytester):
        pytester.makepyfile(MADE_AT_IMPORT)
        result = pytester.runpytest_subprocess("-p", "no:randomly")
        result.assert_outcomes(passed=5, warnings=2)
        # [[] matches a literal [ in fnmatch
        result.stdout.fnmatch_lines(
            [
                "*::test_raised[[]ctx0[]]",
                "*.py:5: ChangeWarning: state[[]'n']: wasn't checked because the block raised*",
                "*::test_raised[[]ctx1[]]",
                "*.py:5: ChangeWarning: same: wasn't checked because the block raised*",
            ]
        )
