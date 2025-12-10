# shared_models/tests/unit/test_api_schemas.py
"""Unit tests for API schemas validation."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest


class TestTelegramUserSchemas:
    """Tests for TelegramUser schemas."""

    def test_create_user_minimal(self):
        """Test creating user with minimal data."""
        from shared_models.api_schemas import TelegramUserCreate

        user = TelegramUserCreate(telegram_id=12345)

        assert user.telegram_id == 12345
        assert user.username is None
        assert user.is_active is True

    def test_create_user_full(self):
        """Test creating user with all fields."""
        from shared_models.api_schemas import TelegramUserCreate

        user = TelegramUserCreate(
            telegram_id=12345,
            username="test_user",
            is_active=False,
        )

        assert user.telegram_id == 12345
        assert user.username == "test_user"
        assert user.is_active is False

    def test_update_user_partial(self):
        """Test partial user update."""
        from shared_models.api_schemas import TelegramUserUpdate

        update = TelegramUserUpdate(username="new_name")

        assert update.username == "new_name"
        assert update.is_active is None  # Not set

    def test_read_user(self):
        """Test user read schema."""
        from shared_models.api_schemas import TelegramUserRead

        user = TelegramUserRead(
            id=1,
            telegram_id=12345,
            username="test_user",
            is_active=True,
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, tzinfo=UTC),
        )

        assert user.id == 1
        assert user.telegram_id == 12345
        assert user.username == "test_user"
        assert user.is_active is True

    def test_timestamp_schema_rejects_naive_datetime(self):
        """Ensure schemas require timezone-aware datetime."""
        from shared_models.api_schemas import AssistantRead

        with pytest.raises(ValueError):
            AssistantRead(
                id=uuid4(),
                name="Test Assistant",
                model="gpt-4",
                is_secretary=False,
                assistant_type=None,
                is_active=True,
                tools=[],
                created_at=datetime(2025, 1, 1),
                updated_at=datetime(2025, 1, 2),
            )


class TestReminderSchemas:
    """Tests for Reminder schemas."""

    def test_create_reminder_one_time(self):
        """Test creating one-time reminder."""
        from shared_models.api_schemas import ReminderCreate
        from shared_models.enums import ReminderStatus, ReminderType

        assistant_id = uuid4()
        trigger_time = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)

        reminder = ReminderCreate(
            user_id=1,
            assistant_id=assistant_id,
            type=ReminderType.ONE_TIME,
            trigger_at=trigger_time,
            payload={"text": "Reminder message"},
        )

        assert reminder.user_id == 1
        assert reminder.assistant_id == assistant_id
        assert reminder.type == ReminderType.ONE_TIME
        assert reminder.trigger_at == trigger_time
        assert reminder.payload == {"text": "Reminder message"}
        assert reminder.status == ReminderStatus.ACTIVE

    def test_create_reminder_recurring(self):
        """Test creating recurring reminder."""
        from shared_models.api_schemas import ReminderCreate
        from shared_models.enums import ReminderType

        reminder = ReminderCreate(
            user_id=1,
            assistant_id=uuid4(),
            type=ReminderType.RECURRING,
            cron_expression="0 9 * * *",
            payload={"text": "Daily reminder"},
        )

        assert reminder.type == ReminderType.RECURRING
        assert reminder.cron_expression == "0 9 * * *"
        assert reminder.trigger_at is None

    def test_payload_from_json_string(self):
        """Test payload validation from JSON string."""
        from shared_models.api_schemas import ReminderCreate
        from shared_models.enums import ReminderType

        reminder = ReminderCreate(
            user_id=1,
            assistant_id=uuid4(),
            type=ReminderType.ONE_TIME,
            trigger_at=datetime.now(UTC),
            payload='{"text": "From JSON string"}',
        )

        assert reminder.payload == {"text": "From JSON string"}

    def test_payload_invalid_json_raises(self):
        """Test that invalid JSON payload raises error."""
        from shared_models.api_schemas import ReminderCreate
        from shared_models.enums import ReminderType

        with pytest.raises(ValueError, match="valid JSON"):
            ReminderCreate(
                user_id=1,
                assistant_id=uuid4(),
                type=ReminderType.ONE_TIME,
                trigger_at=datetime.now(UTC),
                payload="not valid json",
            )

    def test_payload_invalid_type_raises(self):
        """Test that invalid payload type raises error."""
        from shared_models.api_schemas import ReminderCreate
        from shared_models.enums import ReminderType

        with pytest.raises(TypeError, match="must be a dict"):
            ReminderCreate(
                user_id=1,
                assistant_id=uuid4(),
                type=ReminderType.ONE_TIME,
                trigger_at=datetime.now(UTC),
                payload=12345,  # Invalid type
            )

    def test_reminder_status_values(self):
        """Test all reminder status values."""
        from shared_models.enums import ReminderStatus

        assert ReminderStatus.ACTIVE == "active"
        assert ReminderStatus.PAUSED == "paused"
        assert ReminderStatus.COMPLETED == "completed"
        assert ReminderStatus.CANCELLED == "cancelled"

    def test_reminder_update(self):
        """Test reminder update schema."""
        from shared_models.api_schemas import ReminderUpdate
        from shared_models.enums import ReminderStatus

        update = ReminderUpdate(status=ReminderStatus.COMPLETED)

        assert update.status == ReminderStatus.COMPLETED

    def test_reminder_read(self):
        """Test reminder read schema."""
        from shared_models.api_schemas import ReminderRead
        from shared_models.enums import ReminderStatus, ReminderType

        reminder_id = uuid4()
        assistant_id = uuid4()

        reminder = ReminderRead(
            id=reminder_id,
            user_id=1,
            assistant_id=assistant_id,
            type=ReminderType.ONE_TIME,
            trigger_at=datetime(2025, 6, 1, tzinfo=UTC),
            timezone="Europe/Moscow",
            payload={"text": "Test"},
            status=ReminderStatus.ACTIVE,
            last_triggered_at=None,
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, tzinfo=UTC),
        )

        assert reminder.id == reminder_id
        assert reminder.timezone == "Europe/Moscow"

    def test_reminder_timezone_validation(self):
        """Timezone must be valid IANA name or None."""
        from shared_models.api_schemas import ReminderCreate
        from shared_models.enums import ReminderType

        reminder = ReminderCreate(
            user_id=1,
            assistant_id=uuid4(),
            type=ReminderType.RECURRING,
            cron_expression="0 9 * * *",
            timezone="UTC",
            payload={"text": "Test"},
        )

        assert reminder.timezone == "UTC"

        with pytest.raises(ValueError, match="Unknown timezone"):
            ReminderCreate(
                user_id=1,
                assistant_id=uuid4(),
                type=ReminderType.RECURRING,
                cron_expression="0 9 * * *",
                timezone="Invalid/Zone",
                payload={"text": "Test"},
            )


class TestAssistantSchemas:
    """Tests for Assistant schemas."""

    def test_create_assistant_minimal(self):
        """Test creating assistant with minimal data."""
        from shared_models.api_schemas import AssistantCreate

        assistant = AssistantCreate(
            name="Test Assistant",
            model="gpt-4",
        )

        assert assistant.name == "Test Assistant"
        assert assistant.model == "gpt-4"
        assert assistant.is_secretary is False
        assert assistant.is_active is True

    def test_create_assistant_full(self):
        """Test creating assistant with all fields."""
        from shared_models.api_schemas import AssistantCreate
        from shared_models.enums import AssistantType

        assistant = AssistantCreate(
            name="Secretary Bot",
            model="gpt-4o",
            is_secretary=True,
            instructions="You are a helpful secretary.",
            description="Main secretary assistant",
            startup_message="Hello! I'm your secretary.",
            assistant_type=AssistantType.LLM,
            is_active=True,
        )

        assert assistant.is_secretary is True
        assert assistant.instructions == "You are a helpful secretary."
        assert assistant.assistant_type == AssistantType.LLM

    def test_assistant_read_with_tools(self):
        """Test assistant read schema with tools."""
        from shared_models.api_schemas import AssistantRead, ToolRead
        from shared_models.enums import AssistantType, ToolType

        assistant_id = uuid4()
        tool_id = uuid4()

        tool = ToolRead(
            id=tool_id,
            name="calendar_tool",
            tool_type=ToolType.CALENDAR,
            is_active=True,
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, tzinfo=UTC),
        )

        assistant = AssistantRead(
            id=assistant_id,
            name="Test Assistant",
            model="gpt-4",
            is_secretary=False,
            assistant_type=AssistantType.LLM,
            is_active=True,
            tools=[tool],
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, tzinfo=UTC),
        )

        assert len(assistant.tools) == 1
        assert assistant.tools[0].name == "calendar_tool"


class TestToolSchemas:
    """Tests for Tool schemas."""

    def test_create_tool(self):
        """Test creating tool."""
        from shared_models.api_schemas import ToolCreate
        from shared_models.enums import ToolType

        tool = ToolCreate(
            name="reminder_tool",
            tool_type=ToolType.REMINDER_CREATE,
            description="Creates reminders",
        )

        assert tool.name == "reminder_tool"
        assert tool.tool_type == ToolType.REMINDER_CREATE
        assert tool.is_active is True

    def test_tool_types(self):
        """Test all tool types."""
        from shared_models.enums import ToolType

        expected_types = [
            "calendar",
            "reminder_create",
            "reminder_list",
            "reminder_delete",
            "time",
            "sub_assistant",
            "weather",
            "web_search",
            "memory_save",
            "memory_search",
        ]

        actual_types = [t.value for t in ToolType]
        for expected in expected_types:
            assert expected in actual_types


class TestEnums:
    """Tests for enum values."""

    def test_assistant_type_enum(self):
        """Test AssistantType enum."""
        from shared_models.enums import AssistantType

        assert AssistantType.LLM == "llm"

    def test_reminder_type_enum(self):
        """Test ReminderType enum."""
        from shared_models.enums import ReminderType

        assert ReminderType.ONE_TIME == "one_time"
        assert ReminderType.RECURRING == "recurring"
