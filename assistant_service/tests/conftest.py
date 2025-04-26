import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load environment variables from .env.test file at the tests/ level
# Assuming .env.test will be located alongside this conftest.py
test_env_path = Path(__file__).parent / ".env.test"
if test_env_path.exists():
    load_dotenv(test_env_path)
else:
    # Fallback to main .env in the project root if test env not found here
    # Go up two levels from assistant_service/tests/ to project root
    project_root_env = Path(__file__).parent.parent.parent / ".env"
    if project_root_env.exists():
        load_dotenv(project_root_env)
    else:
        print(f"Warning: No .env file found at {test_env_path} or {project_root_env}")


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "external_api: mark test as using external API (deselected by default)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip external_api tests by default unless explicitly requested."""
    if not config.getoption("--run-external"):
        skip_external = pytest.mark.skip(reason="need --run-external option to run")
        for item in items:
            if "external_api" in item.keywords:
                item.add_marker(skip_external)


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-external",
        action="store_true",
        default=False,
        help="run tests that use external APIs",
    )


# Basic event loop fixture, often needed for async tests
@pytest.fixture(scope="session")
def event_loop():
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
