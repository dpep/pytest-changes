from datetime import timedelta
from decimal import Decimal

import pytest

from pytest_changes import ChangeAssertionError, changes, unchanged


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
        assert message(e) == "counter.value: expected → 20, got 0 → 15"

    def test_strings(self):
        user = Counter("pending")
        with pytest.raises(ChangeAssertionError) as e, changes(user, "value", to="active"):
            user.value = "banned"
        assert message(e) == "user.value: expected → 'active', got 'pending' → 'banned'"

    def test_requires_a_change(self):
        user = Counter("active")
        with pytest.raises(ChangeAssertionError) as e, changes(user, "value", to="active"):
            pass
        assert (
            message(e) == "user.value: expected to change to 'active', but it was already 'active'"
        )

    def test_stayed_away_from_the_target(self, counter):
        with pytest.raises(ChangeAssertionError) as e, changes(counter, "value", to=20):
            pass
        assert message(e) == "counter.value: expected → 20, stayed 0"


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

    @pytest.mark.parametrize("zero", [0, 0.0])
    def test_zero_raises_at_construction(self, counter, zero):
        with pytest.raises(TypeError) as e:
            changes(counter, "value", by=zero)
        assert str(e.value) == f"changes() with by={zero} asserts no change; use unchanged()"

    def test_matcher_for_zero_raises_at_construction(self, counter):
        with pytest.raises(TypeError, match=r"asserts no change; use unchanged\(\)"):
            changes(counter, "value", by=pytest.approx(0))

    def test_neither_sized_nor_subtractable(self):
        user = Counter(object())
        with pytest.raises(TypeError) as e, changes(user, "value", by=1):
            user.value = object()
        assert str(e.value) == (
            "user.value: by= needs values with a length or that subtract (object - object failed)"
        )
        assert e.value.__suppress_context__

    def test_cannot_subtract_traceback_ends_at_the_with_line(self, pytester):
        pytester.makepyfile(
            """
            from pytest_changes import changes

            def test_it():
                box = [object()]
                with changes(lambda: box[0], by=1):
                    box[0] = object()
            """
        )
        result = pytester.runpytest_subprocess()
        result.assert_outcomes(failed=1)
        assert "_core.py" not in result.stdout.str()
        assert "direct cause" not in result.stdout.str()

    def test_matcher(self):
        total = Counter(0.1)
        with changes(total, "value", by=pytest.approx(0.2)):
            total.value += 0.2


class TestByLength:
    def test_counts_items_added(self):
        books = ["a"]
        with changes(lambda: books, by=1):
            books.append("b")

    def test_counts_items_removed(self):
        books = ["a", "b"]
        with changes(lambda: books, by=-1):
            books.pop()

    def test_sets_count_rather_than_subtract(self):
        tags = {"a"}
        with changes(lambda: tags, by=1):
            tags.add("b")

    def test_strings_count_characters(self):
        log = Counter("ab")
        with changes(log, "value", by=3):
            log.value += "cde"

    def test_length_wins_over_subtraction(self):
        box = Counter(Sized(1))
        with changes(box, "value", by=1):
            box.value = Sized(2, sub=100)

    def test_unsized_len_falls_back_to_subtraction(self):
        # numpy's 0-d arrays define __len__ but raise TypeError from it
        box = Counter(Unsized(1))
        with changes(box, "value", by=100):
            box.value = Unsized(2, sub=100)

    def test_fails_with_lengths(self):
        lib = Counter(["a", "b", "c"])
        with pytest.raises(ChangeAssertionError) as e, changes(lambda: lib.value, by=1):
            lib.value += ["d", "e"]
        assert message(e) == "lib.value: expected Δ +1, got Δ +2 (len 3 → 5)"

    def test_same_length_different_items(self):
        books = ["a"]
        with pytest.raises(ChangeAssertionError) as e, changes(lambda: books, by=1):
            books[0] = "b"
        assert message(e) == "books: expected Δ +1, got Δ +0 (len 1 → 1)"

    def test_did_not_change(self):
        books = ["a", "b", "c"]
        with pytest.raises(ChangeAssertionError) as e, changes(lambda: books, by=1):
            pass
        assert message(e) == "books: expected Δ +1, did not change (len stayed 3)"

    def test_long_values_stay_out_of_the_message(self):
        books = list(range(100))
        with pytest.raises(ChangeAssertionError) as e, changes(lambda: books, by=1):
            books.extend([1, 2])
        assert message(e) == "books: expected Δ +1, got Δ +2 (len 100 → 102)"


class Sized:
    """Sized and subtractable, like a numpy array; `-` returns `sub`."""

    def __init__(self, n, sub=0):
        self.n, self.sub = n, sub

    def __len__(self):
        return self.n

    def __sub__(self, other):
        return self.sub

    def __eq__(self, other):
        return self.n == other.n


class Unsized(Sized):
    def __len__(self):
        raise TypeError("len() of unsized object")


class TestMessages:
    def test_stayed_shortens_long_values(self):
        items = list(range(30))
        with pytest.raises(ChangeAssertionError) as e, changes(lambda: items):
            pass
        assert (
            message(e)
            == "items: expected to change, stayed [0, 1, 2, 3, 4, 5,...5, 26, 27, 28, 29]"
        )

    def test_by_shortens_long_values(self):
        big = Counter(10**50)
        with pytest.raises(ChangeAssertionError) as e, changes(big, "value", by=1):
            big.value += 2
        assert message(e) == (
            "big.value: expected Δ +1, got Δ +2 "
            "(100000000000000000...000000000000000000 → 100000000000000000...000000000000000002)"
        )

    def test_by_shortens_long_values_that_stayed(self):
        big = Counter(10**50)
        with pytest.raises(ChangeAssertionError) as e, changes(big, "value", by=1):
            pass
        assert message(e) == (
            "big.value: expected Δ +1, did not change (stayed 100000000000000000...000000000000000000)"
        )

    def test_timedelta_deltas_read_as_durations(self):
        elapsed = Counter(timedelta(0))
        with (
            pytest.raises(ChangeAssertionError) as e,
            changes(elapsed, "value", by=timedelta(hours=1)),
        ):
            elapsed.value += timedelta(hours=2)
        assert message(e) == (
            "elapsed.value: expected Δ 1:00:00, got Δ 2:00:00 "
            "(datetime.timedelta(0) → datetime.timedelta(seconds=7200))"
        )

    def test_decimal_deltas_are_signed(self):
        price = Counter(Decimal("1.00"))
        with pytest.raises(ChangeAssertionError) as e, changes(price, "value", by=Decimal("0.50")):
            price.value += Decimal("0.25")
        assert message(e) == (
            "price.value: expected Δ +0.50, got Δ +0.25 (Decimal('1.00') → Decimal('1.25'))"
        )

    def test_string_expectations_keep_their_quotes(self, counter):
        with pytest.raises(ChangeAssertionError) as e, changes(counter, "value", by="1"):
            counter.value += 1
        assert message(e) == "counter.value: expected Δ '1', got Δ +1 (0 → 1)"


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

    def test_delta_counts_items(self):
        books = ["a"]
        with changes(lambda: books) as c:
            books.append("b")
        assert c.delta == 1

    def test_delta_of_values_neither_sized_nor_subtractable_raises(self):
        shelf = Counter(None)
        with changes(shelf, "value") as c:
            shelf.value = 1
        with pytest.raises(TypeError) as e:
            c.delta  # noqa: B018
        assert str(e.value) == (
            "shelf.value: delta needs values with a length or that subtract (int - NoneType failed)"
        )

    def test_values_are_unset_until_read(self, counter):
        c = changes(counter, "value")
        with pytest.raises(AttributeError, match="read when the with block is entered"):
            c.before  # noqa: B018
        with c:
            counter.value = 1
            with pytest.raises(AttributeError, match="read when the with block exits"):
                c.after  # noqa: B018
            with pytest.raises(AttributeError, match="read when the with block exits"):
                c.delta  # noqa: B018

    def test_after_is_read_when_the_block_raises(self, counter):
        with pytest.raises(ValueError), changes(counter, "value") as c:
            counter.value = 1
            raise ValueError
        assert (c.before, c.after) == (0, 1)

    def test_after_is_unset_when_the_test_is_skipped(self, counter):
        with pytest.raises(pytest.skip.Exception), changes(counter, "value") as c:
            pytest.skip("not today")
        assert not hasattr(c, "after")


class TestBlockErrors:
    def test_change_made_lets_the_error_through_untouched(self, counter):
        error = ValueError()
        with pytest.raises(ValueError) as e, changes(counter, "value", by=1):
            counter.value += 1
            raise error
        assert e.value is error

    def test_change_missing_fails_chained_from_the_block_error(self, counter):
        with pytest.raises(ChangeAssertionError) as e, changes(counter, "value", by=1):
            raise ValueError
        assert message(e) == "counter.value: expected Δ +1, did not change (stayed 0)"
        assert isinstance(e.value.__cause__, ValueError)

    def test_plain_assertion_errors_pass_through(self, counter):
        with pytest.raises(AssertionError) as e, changes(counter, "value", by=1):
            counter.value += 1
            raise AssertionError("mine")
        assert type(e.value) is AssertionError

    def test_control_flow_exceptions_skip_the_check(self, counter):
        with pytest.raises(pytest.skip.Exception), changes(counter, "value", by=1):
            pytest.skip("not today")


class TestInvalidCombos:
    def test_to_and_by(self, counter):
        with pytest.raises(TypeError, match="cannot combine to and by"):
            changes(counter, "value", to=1, by=1)


class TestSignature:
    @pytest.mark.parametrize("make", [changes, unchanged])
    def test_getter_and_attr_are_positional_only(self, counter, make):
        with pytest.raises(TypeError, match="positional"):
            make(getter=counter, attr="value")
