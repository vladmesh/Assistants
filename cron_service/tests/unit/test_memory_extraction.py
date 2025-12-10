"""Unit tests for memory extraction job."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock openai module before importing memory_extraction
sys.modules["openai"] = MagicMock()

from src.jobs.memory_extraction import (  # noqa: E402
    ExtractionResult,
    MemoryExtractionJob,
)


@pytest.fixture
def memory_extraction_job():
    """Create a MemoryExtractionJob instance for testing."""
    return MemoryExtractionJob()


@pytest.fixture
def sample_settings():
    """Sample global settings for memory extraction."""
    return {
        "memory_extraction_enabled": True,
        "memory_extraction_interval_hours": 24,
        "memory_extraction_model": "gpt-4o-mini",
        "memory_extraction_provider": "openai",
        "memory_dedup_threshold": 0.85,
        "memory_update_threshold": 0.95,
        "embedding_model": "text-embedding-3-small",
    }


@pytest.fixture
def sample_conversation():
    """Sample conversation data."""
    return {
        "user_id": 123,
        "assistant_id": "test-assistant-uuid",
        "messages": [
            {
                "id": 1,
                "role": "user",
                "content": "Привет! Меня зовут Алексей, я программист из Москвы.",
                "timestamp": "2024-12-10T10:00:00Z",
            },
            {
                "id": 2,
                "role": "assistant",
                "content": "Привет, Алексей! Рад познакомиться.",
                "timestamp": "2024-12-10T10:00:05Z",
            },
            {
                "id": 3,
                "role": "user",
                "content": "Я люблю Python и FastAPI.",
                "timestamp": "2024-12-10T10:01:00Z",
            },
        ],
        "message_count": 3,
        "earliest_timestamp": "2024-12-10T10:00:00Z",
        "latest_timestamp": "2024-12-10T10:01:00Z",
    }


class TestMemoryExtractionJob:
    """Tests for MemoryExtractionJob class."""

    def test_format_conversation(self, memory_extraction_job, sample_conversation):
        """Test conversation formatting for prompt."""
        result = memory_extraction_job._format_conversation(sample_conversation)

        assert "user:" in result
        assert "assistant:" in result
        assert "Алексей" in result
        assert "Python" in result

    def test_format_existing_facts_empty(self, memory_extraction_job):
        """Test formatting when no existing facts."""
        result = memory_extraction_job._format_existing_facts([])
        assert result == "Нет известных фактов."

    def test_format_existing_facts_with_data(self, memory_extraction_job):
        """Test formatting with existing facts."""
        facts = [
            {"text": "Пользователя зовут Алексей", "memory_type": "user_fact"},
            {"text": "Любит Python", "memory_type": "preference"},
        ]
        result = memory_extraction_job._format_existing_facts(facts)

        assert "[user_fact] Пользователя зовут Алексей" in result
        assert "[preference] Любит Python" in result

    def test_parse_extraction_result_valid_json(self, memory_extraction_job):
        """Test parsing valid JSON extraction result."""
        content = json.dumps(
            [
                {
                    "text": "Имя пользователя - Алексей",
                    "memory_type": "user_fact",
                    "importance": 8,
                },
                {"text": "Живет в Москве", "memory_type": "user_fact", "importance": 6},
            ]
        )
        user_id = 123

        results = memory_extraction_job._parse_extraction_result(content, user_id)

        assert len(results) == 2
        assert results[0].text == "Имя пользователя - Алексей"
        assert results[0].memory_type == "user_fact"
        assert results[0].importance == 8
        assert results[0].user_id == 123
        assert results[1].text == "Живет в Москве"

    def test_parse_extraction_result_invalid_json(self, memory_extraction_job):
        """Test parsing invalid JSON returns empty list."""
        content = "This is not valid JSON"
        user_id = 123

        results = memory_extraction_job._parse_extraction_result(content, user_id)

        assert results == []

    def test_parse_extraction_result_empty_list(self, memory_extraction_job):
        """Test parsing empty JSON array."""
        content = "[]"
        user_id = 123

        results = memory_extraction_job._parse_extraction_result(content, user_id)

        assert results == []

    def test_parse_extraction_result_invalid_memory_type(self, memory_extraction_job):
        """Test that invalid memory_type is corrected to user_fact."""
        content = json.dumps(
            [{"text": "Some fact", "memory_type": "invalid_type", "importance": 5}]
        )
        user_id = 123

        results = memory_extraction_job._parse_extraction_result(content, user_id)

        assert len(results) == 1
        assert results[0].memory_type == "user_fact"

    def test_parse_extraction_result_importance_bounds(self, memory_extraction_job):
        """Test that importance is bounded between 1 and 10."""
        content = json.dumps(
            [
                {"text": "Fact 1", "memory_type": "user_fact", "importance": 0},
                {"text": "Fact 2", "memory_type": "user_fact", "importance": 15},
                {"text": "Fact 3", "memory_type": "user_fact", "importance": "invalid"},
            ]
        )
        user_id = 123

        results = memory_extraction_job._parse_extraction_result(content, user_id)

        assert len(results) == 3
        assert results[0].importance == 1  # Bounded from 0
        assert results[1].importance == 10  # Bounded from 15
        assert results[2].importance == 1  # Default for invalid

    def test_parse_extraction_result_skips_empty_text(self, memory_extraction_job):
        """Test that facts with empty text are skipped."""
        content = json.dumps(
            [
                {"text": "", "memory_type": "user_fact", "importance": 5},
                {"text": "Valid fact", "memory_type": "user_fact", "importance": 5},
                {"text": "   ", "memory_type": "user_fact", "importance": 5},
            ]
        )
        user_id = 123

        results = memory_extraction_job._parse_extraction_result(content, user_id)

        assert len(results) == 1
        assert results[0].text == "Valid fact"


class TestExtractionResult:
    """Tests for ExtractionResult dataclass."""

    def test_extraction_result_creation(self):
        """Test creating ExtractionResult."""
        result = ExtractionResult(
            text="Test fact",
            memory_type="user_fact",
            importance=7,
            user_id=123,
            assistant_id="test-uuid",
        )

        assert result.text == "Test fact"
        assert result.memory_type == "user_fact"
        assert result.importance == 7
        assert result.user_id == 123
        assert result.assistant_id == "test-uuid"

    def test_extraction_result_default_assistant_id(self):
        """Test that assistant_id defaults to None."""
        result = ExtractionResult(
            text="Test fact",
            memory_type="preference",
            importance=5,
            user_id=456,
        )

        assert result.assistant_id is None


@pytest.mark.asyncio
class TestMemoryExtractionJobAsync:
    """Async tests for MemoryExtractionJob."""

    @patch("src.jobs.memory_extraction.fetch_global_settings")
    async def test_get_settings_returns_fetched(self, mock_fetch, sample_settings):
        """Test that _get_settings returns fetched settings."""
        mock_fetch.return_value = sample_settings
        job = MemoryExtractionJob()

        settings = await job._get_settings()

        assert settings == sample_settings

    @patch("src.jobs.memory_extraction.fetch_global_settings")
    async def test_get_settings_returns_defaults_on_failure(self, mock_fetch):
        """Test that _get_settings returns defaults when fetch fails."""
        mock_fetch.return_value = None
        job = MemoryExtractionJob()

        settings = await job._get_settings()

        assert settings["memory_extraction_enabled"] is True
        assert settings["memory_extraction_model"] == "gpt-4o-mini"

    @patch("src.jobs.memory_extraction.fetch_global_settings")
    async def test_run_disabled_extraction(self, mock_fetch):
        """Test that run exits early when extraction is disabled."""
        mock_fetch.return_value = {"memory_extraction_enabled": False}
        job = MemoryExtractionJob()

        stats = await job.run()

        assert stats["status"] == "disabled"

    @patch("src.jobs.memory_extraction.fetch_conversations")
    @patch("src.jobs.memory_extraction.fetch_pending_batch_jobs")
    @patch("src.jobs.memory_extraction.fetch_global_settings")
    async def test_run_no_conversations(
        self, mock_settings, mock_pending, mock_conversations, sample_settings
    ):
        """Test run when no new conversations."""
        mock_settings.return_value = sample_settings
        mock_pending.return_value = []
        mock_conversations.return_value = []
        job = MemoryExtractionJob()

        stats = await job.run()

        assert stats["status"] == "no_new_data"
        assert stats["conversations_processed"] == 0
