import pytest

from pytest_changes import ChangeAssertionError, _plugin, changes, unchanged

pytest_plugins = ["pytester"]


class Cart:
    def __init__(self, size=30):
        self.items = list(range(size))
        self.total = 0


@pytest.fixture(autouse=True)
def default_verbosity(request, monkeypatch):
    # pytest's explanation depends on -v and on running in CI; pin both
    monkeypatch.setattr(request.config.option, "verbose", 0)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("BUILD_NUMBER", raising=False)


def test_to_mismatch_explains_like_assert():
    cart = Cart()
    with pytest.raises(ChangeAssertionError) as e, changes(cart, "items", to=[*range(30), 99]):
        cart.items.append(30)
    assert str(e.value) == (
        "cart.items: expected → [0, 1, 2, 3, 4, 5,...6, 27, 28, 29, 99], "
        "got [0, 1, 2, 3, 4, 5,...5, 26, 27, 28, 29] → [0, 1, 2, 3, 4, 5,...6, 27, 28, 29, 30]\n"
        "  At index 30 diff: 30 != 99\n"
        "  Use -v to get more diff"
    )


def test_unchanged_explains_after_against_before():
    config = {f"key{i}": i for i in range(10)}
    with pytest.raises(ChangeAssertionError) as e, unchanged(lambda: config):
        config["key3"] = 99
    assert str(e.value).splitlines()[1:] == [
        "  Omitting 9 identical items, use -vv to show",
        "  Differing items:",
        "  {'key3': 99} != {'key3': 3}",
        "  Use -v to get more diff",
    ]


def test_short_values_stay_on_one_line():
    cart = Cart(size=2)
    with pytest.raises(ChangeAssertionError) as e, changes(cart, "items", to=[0, 1, 2]):
        cart.items.append(3)
    assert str(e.value) == "cart.items: expected → [0, 1, 2], got [0, 1] → [0, 1, 3]"


def test_stacked_explanation_sits_under_its_own_line():
    cart = Cart()
    with (
        pytest.raises(ChangeAssertionError) as e,
        changes(cart, "items", to=[]),
        changes(cart, "total", by=20),
    ):
        cart.items.pop()
        cart.total += 15
    assert str(e.value) == (
        "2 change expectations failed\n"
        "  ✗ cart.items  expected → [], got [0, 1, 2, 3, 4, 5,...5, 26, 27, 28, 29] "
        "→ [0, 1, 2, 3, 4, 5,...4, 25, 26, 27, 28]\n"
        "                Left contains 29 more items, first extra item: 0\n"
        "                Use -v to get more diff\n"
        "  ✗ cart.total  expected Δ +20, got Δ +15 (0 → 15)"
    )


def test_outside_pytest_keeps_the_one_line_message(monkeypatch):
    monkeypatch.setattr(_plugin, "_configs", [])
    cart = Cart(size=12)
    with pytest.raises(ChangeAssertionError) as e, unchanged(cart, "items"):
        cart.items.append(12)
    assert str(e.value) == (
        f"cart.items: expected no change, got {list(range(12))!r} → {list(range(13))!r}"
    )


def test_broken_explanation_hook_keeps_the_one_line_message(request):
    class Broken:
        @staticmethod
        def pytest_assertrepr_compare(config, op, left, right):
            raise RuntimeError("boom")

    plugin = Broken()
    request.config.pluginmanager.register(plugin)
    request.addfinalizer(lambda: request.config.pluginmanager.unregister(plugin))
    cart = Cart(size=12)
    with pytest.raises(ChangeAssertionError) as e, unchanged(cart, "items"):
        cart.items.append(12)
    assert "\n" not in str(e.value)


def test_renders_in_a_real_run(pytester):
    pytester.makepyfile(
        """
        from pytest_changes import changes

        def test_it():
            items = list(range(30))
            with changes(lambda: items, to=[*range(30), 99]):
                items.append(30)
        """
    )
    result = pytester.runpytest_subprocess()
    result.stdout.fnmatch_lines(
        [
            "E *ChangeAssertionError: items: expected → [0, 1, 2, *",
            "E *  At index 30 diff: 30 != 99",
            "E *  Use -v to get more diff",
        ]
    )

    result = pytester.runpytest_subprocess("-vv")
    result.stdout.fnmatch_lines(
        [
            "E *  Full diff:*",
            "E *  -     99,",
            "E *  +     30,",
        ]
    )
