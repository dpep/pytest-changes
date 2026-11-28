from hypothesis import given
from hypothesis import strategies as st

from pytest_changes import ChangeAssertionError, changes, unchanged


class Box:
    def __init__(self, value):
        self.value = value


def passes(context, box, after):
    try:
        with context:
            box.value = after
    except ChangeAssertionError:
        return False
    return True


@given(st.integers(), st.integers(), st.integers().filter(bool))
def test_by_passes_iff_delta_matches(before, after, by):
    box = Box(before)
    assert passes(changes(box, "value", by=by), box, after) == (after - before == by)


@given(st.integers(), st.integers())
def test_unchanged_is_the_negation_of_changes(before, after):
    a, b = Box(before), Box(before)
    assert passes(unchanged(a, "value"), a, after) != passes(changes(b, "value"), b, after)
