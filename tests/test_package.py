import pytest_changes


def test_version():
    assert pytest_changes.__version__


def test_errors_show_the_public_module():
    assert pytest_changes.ChangeAssertionError.__module__ == "pytest_changes"


def test_a_failed_configure_reports_only_its_own_error(pytester):
    pytester.makeconftest(
        """
        def pytest_configure(config):
            raise RuntimeError("the real problem")
        """
    )
    result = pytester.runpytest_subprocess()
    assert "RuntimeError: the real problem" in result.stderr.str()
    assert "pytest_changes" not in result.stderr.str()
