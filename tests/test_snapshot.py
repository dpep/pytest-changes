import pytest

from pytest_changes import ChangeAssertionError, changes, unchanged


class Cart:
    def __init__(self):
        self.items = []


class TestInPlaceMutation:
    def test_append_counts_as_a_change(self):
        cart = Cart()
        with changes(cart, "items"):
            cart.items.append("x")

    def test_append_fails_unchanged(self):
        cart = Cart()
        with pytest.raises(ChangeAssertionError) as e, unchanged(cart, "items"):
            cart.items.append("x")
        assert str(e.value) == "<Cart>.items: expected no change, got [] → ['x']"
