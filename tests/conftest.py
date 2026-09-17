# conftest.py
import pytest

@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    return {
        **browser_type_launch_args,
        "args": [
            "--disable-web-security",
            "--allow-running-insecure-content",
            "--disable-site-isolation-trials"
        ]
    }# Add Pytest fixtures here
