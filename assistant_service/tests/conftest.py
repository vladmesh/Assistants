import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from openai import OpenAI

# Load environment variables from .env.test file
test_env_path = Path(__file__).parent / ".env.test"
if test_env_path.exists():
    load_dotenv(test_env_path)
else:
    # Fallback to main .env if test env not found
    load_dotenv()

# Add src to PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


@pytest.fixture
def llm():
    """Фикстура для LangChain ChatOpenAI модели"""
    return ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.7)


@pytest.fixture
def openai_client():
    """Фикстура для нативного OpenAI клиента"""
    return OpenAI()


@pytest.fixture
def openai_assistant_id():
    """ID ассистента OpenAI для тестов"""
    return os.getenv("OPENAI_ASSISTANT_ID")


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
