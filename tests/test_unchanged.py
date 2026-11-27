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
    assert str(e.value) == "<Counter>.value: expected no change, got 4 → 5 (Δ +1)"


def test_omits_delta_when_values_cannot_subtract():
    user = Counter("a")
    with pytest.raises(ChangeAssertionError) as e, unchanged(lambda: user.value, label="user"):
        user.value = "b"
    assert str(e.value) == "user: expected no change, got 'a' → 'b'"


def test_same_object_counts_as_unchanged():
    class Plain:
        pass

    obj = Plain()
    with unchanged(lambda: obj):
        pass
