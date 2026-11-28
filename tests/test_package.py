import pytest_changes


def test_version():
    assert pytest_changes.__version__


def test_errors_show_the_public_module():
    assert pytest_changes.ChangeAssertionError.__module__ == "pytest_changes"
