from datetime import timedelta
from decimal import Decimal
from unittest import mock

import pytest

from pytest_changes import ChangeAssertionError, ChangeWarning, changes, unchanged


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

    @pytest.mark.parametrize("zero", [0, 0.0, Decimal(0)], ids=repr)
    def test_zero_raises_at_construction(self, counter, zero):
        with pytest.raises(TypeError) as e:
            changes(counter, "value", by=zero)
        assert str(e.value) == f"changes() with by={zero!r} asserts no change; use unchanged()"

    @pytest.mark.parametrize(
        ("start", "by"),
        [(0, pytest.approx(0, abs=1)), (0, mock.ANY), (timedelta(0), timedelta(0))],
        ids=["approx", "ANY", "timedelta"],
    )
    def test_non_numbers_that_equal_zero_are_allowed(self, start, by):
        box = Counter(start)
        with changes(box, "value", by=by):
            pass

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


class TestByRange:
    @pytest.mark.parametrize("step", [1, 3])
    def test_passes_inside(self, counter, step):
        with changes(counter, "value", by=range(1, 4)):
            counter.value += step

    def test_fails_outside(self, counter):
        with pytest.raises(ChangeAssertionError) as e, changes(counter, "value", by=range(1, 4)):
            counter.value += 4
        assert message(e) == "counter.value: expected Δ in 1..3, got Δ +4 (0 → 4)"

    def test_negative(self, counter):
        with pytest.raises(ChangeAssertionError) as e, changes(counter, "value", by=range(-3, 0)):
            pass
        assert message(e) == "counter.value: expected Δ in -3..-1, did not change (stayed 0)"

    def test_step(self, counter):
        with pytest.raises(ChangeAssertionError) as e, changes(counter, "value", by=range(0, 9, 2)):
            counter.value += 3
        assert message(e) == "counter.value: expected Δ in range(0, 9, 2), got Δ +3 (0 → 3)"

    def test_counts_items(self):
        lib = Counter(["a"])
        with changes(lib, "value", by=range(1, 3)):
            lib.value = ["a", "b", "c"]

    def test_empty_raises_at_construction(self, counter):
        with pytest.raises(ValueError, match=r"range\(3, 1\) is empty"):
            changes(counter, "value", by=range(3, 1))


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

    def test_non_number_deltas_use_repr(self):
        elapsed = Counter(timedelta(hours=5))
        with (
            pytest.raises(ChangeAssertionError) as e,
            changes(elapsed, "value", by=timedelta(hours=1)),
        ):
            elapsed.value -= timedelta(hours=1)
        assert message(e) == (
            "elapsed.value: expected Δ datetime.timedelta(seconds=3600), "
            "got Δ datetime.timedelta(days=-1, seconds=82800) "
            "(datetime.timedelta(seconds=18000) → datetime.timedelta(seconds=14400))"
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
        assert "after the block" in e.value.__notes__[0]


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

    def test_after_is_unset_when_the_block_raises(self, counter):
        with pytest.warns(ChangeWarning), pytest.raises(ValueError), changes(counter, "value") as c:
            raise ValueError
        with pytest.raises(AttributeError) as e:
            c.after  # noqa: B018
        assert str(e.value) == "after isn't set: it wasn't read because the block raised"

    def test_after_is_unset_when_the_test_is_skipped(self, counter):
        with pytest.raises(pytest.skip.Exception), changes(counter, "value") as c:
            pytest.skip("not today")
        with pytest.raises(AttributeError, match="because the block raised"):
            c.delta  # noqa: B018


class TestBlockErrors:
    def test_skips_the_check_and_lets_the_error_through_untouched(self, counter):
        error = ValueError()
        with (
            pytest.warns(ChangeWarning, match=r"^counter.value: not checked") as record,
            pytest.raises(ValueError) as e,
            changes(counter, "value", by=1),
        ):
            raise error
        assert e.value is error
        assert str(record[0].message).endswith("with changes(...), pytest.raises(ValueError):")

    def test_expectation_outside_pytest_raises_checks_the_error_path(self):
        log = []

        def reject():
            log.append("rejected")
            raise ValueError

        with changes(lambda: len(log), by=1), pytest.raises(ValueError):
            reject()

        with pytest.raises(ChangeAssertionError) as e:  # noqa: SIM117
            with changes(lambda: len(log), by=1), pytest.raises(ValueError):
                raise ValueError
        assert message(e) == "len(log): expected Δ +1, did not change (stayed 1)"

    def test_plain_assertion_errors_pass_through(self, counter):
        with (
            pytest.warns(ChangeWarning),
            pytest.raises(AssertionError) as e,
            changes(counter, "value", by=1),
        ):
            raise AssertionError("mine")
        assert type(e.value) is AssertionError


class TestEnteredOnce:
    def test_nesting_the_same_context_raises(self, counter):
        context = changes(counter, "value", by=2)
        with pytest.warns(ChangeWarning), pytest.raises(RuntimeError) as e, context:  # noqa: SIM117
            with context:
                pass
        assert str(e.value) == (
            "changes() can only be entered once: call changes() again for each with block"
        )

    def test_reuse_raises(self, counter):
        context = unchanged(counter, "value")
        with context:
            pass
        with pytest.raises(RuntimeError, match=r"^unchanged\(\) can only be entered once"):
            context.__enter__()


class TestInvalidCombos:
    def test_to_and_by(self, counter):
        with pytest.raises(TypeError, match="cannot combine to and by"):
            changes(counter, "value", to=1, by=1)


class TestSignature:
    @pytest.mark.parametrize("make", [changes, unchanged])
    def test_getter_and_attr_are_positional_only(self, counter, make):
        with pytest.raises(TypeError, match="positional"):
            make(getter=counter, attr="value")
