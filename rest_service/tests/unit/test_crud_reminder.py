# rest_service/tests/unit/test_crud_reminder.py
"""Unit tests for reminder CRUD operations."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.fixture
def mock_session():
    """Create mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def sample_reminder_create():
    """Sample reminder create data."""
    from shared_models.api_schemas import ReminderCreate
    from shared_models.enums import ReminderStatus, ReminderType

    return ReminderCreate(
        user_id=1,
        assistant_id=uuid4(),
        type=ReminderType.ONE_TIME,
        trigger_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
        payload={"text": "Test reminder"},
        status=ReminderStatus.ACTIVE,
    )


class TestGetReminder:
    """Tests for get_reminder function."""

    @pytest.mark.asyncio
    async def test_reminder_found(self, mock_session):
        """Test getting reminder when exists."""
        from crud.reminder import get_reminder

        reminder_id = uuid4()
        mock_reminder = MagicMock()
        mock_reminder.id = reminder_id
        mock_session.get.return_value = mock_reminder

        result = await get_reminder(mock_session, reminder_id)

        assert result == mock_reminder

    @pytest.mark.asyncio
    async def test_reminder_not_found(self, mock_session):
        """Test getting reminder when not exists."""
        from crud.reminder import get_reminder

        mock_session.get.return_value = None

        result = await get_reminder(mock_session, uuid4())

        assert result is None


class TestGetScheduledReminders:
    """Tests for get_scheduled_reminders function."""

    @pytest.mark.asyncio
    async def test_returns_active_reminders(self, mock_session):
        """Test getting only active reminders."""
        from crud.reminder import get_scheduled_reminders

        mock_reminders = [MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_reminders
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await get_scheduled_reminders(mock_session)

        assert result == mock_reminders

    @pytest.mark.asyncio
    async def test_returns_empty_when_none_active(self, mock_session):
        """Test returns empty list when no active reminders."""
        from crud.reminder import get_scheduled_reminders

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await get_scheduled_reminders(mock_session)

        assert result == []


class TestGetUserReminders:
    """Tests for get_user_reminders function."""

    @pytest.mark.asyncio
    async def test_returns_user_reminders(self, mock_session):
        """Test getting reminders for existing user."""
        from crud.reminder import get_user_reminders

        mock_user = MagicMock()
        mock_session.get.return_value = mock_user

        mock_reminders = [MagicMock()]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_reminders
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await get_user_reminders(mock_session, user_id=1)

        assert result == mock_reminders

    @pytest.mark.asyncio
    async def test_returns_empty_for_nonexistent_user(self, mock_session):
        """Test returns empty list for nonexistent user."""
        from crud.reminder import get_user_reminders

        mock_session.get.return_value = None  # User not found

        result = await get_user_reminders(mock_session, user_id=999)

        assert result == []


class TestCreateReminder:
    """Tests for create_reminder function."""

    @pytest.mark.asyncio
    async def test_create_reminder_success(self, mock_session, sample_reminder_create):
        """Test creating reminder successfully."""
        from crud.reminder import create_reminder

        # Mock user exists
        mock_user = MagicMock()
        mock_session.get.return_value = mock_user

        # Mock the Reminder model
        with patch("crud.reminder.Reminder") as MockReminder:
            mock_reminder = MagicMock()
            mock_reminder.id = uuid4()
            mock_reminder.user_id = sample_reminder_create.user_id
            MockReminder.return_value = mock_reminder

            result = await create_reminder(mock_session, sample_reminder_create)

            assert result == mock_reminder
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_reminder_user_not_found(
        self, mock_session, sample_reminder_create
    ):
        """Test creating reminder fails when user not found."""
        from crud.reminder import create_reminder

        mock_session.get.return_value = None  # User not found

        with pytest.raises(ValueError, match="User not found"):
            await create_reminder(mock_session, sample_reminder_create)

    @pytest.mark.asyncio
    async def test_create_reminder_converts_timezone(self, mock_session):
        """Test that timezone-aware datetime is converted to naive UTC."""
        from shared_models.api_schemas import ReminderCreate
        from shared_models.enums import ReminderType

        from crud.reminder import create_reminder

        # Mock user exists
        mock_user = MagicMock()
        mock_session.get.return_value = mock_user

        # Create reminder with timezone-aware datetime
        trigger_time = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
        reminder_in = ReminderCreate(
            user_id=1,
            assistant_id=uuid4(),
            type=ReminderType.ONE_TIME,
            trigger_at=trigger_time,
            payload={"text": "Test"},
        )

        with patch("crud.reminder.Reminder") as MockReminder:
            mock_reminder = MagicMock()
            MockReminder.return_value = mock_reminder

            await create_reminder(mock_session, reminder_in)

            # Verify Reminder was created with trigger_at
            call_kwargs = MockReminder.call_args[1]
            # trigger_at should be naive (tzinfo removed)
            assert call_kwargs["trigger_at"].tzinfo is None


class TestUpdateReminderStatus:
    """Tests for update_reminder_status function."""

    @pytest.mark.asyncio
    async def test_update_status_success(self, mock_session):
        """Test updating reminder status successfully."""
        from shared_models.enums import ReminderStatus

        from crud.reminder import update_reminder_status

        reminder_id = uuid4()
        mock_reminder = MagicMock()
        mock_reminder.status = ReminderStatus.ACTIVE
        mock_session.get.return_value = mock_reminder

        result = await update_reminder_status(
            mock_session, reminder_id, ReminderStatus.COMPLETED
        )

        assert result == mock_reminder
        assert mock_reminder.status == ReminderStatus.COMPLETED
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_not_found(self, mock_session):
        """Test updating nonexistent reminder returns None."""
        from shared_models.enums import ReminderStatus

        from crud.reminder import update_reminder_status

        mock_session.get.return_value = None

        result = await update_reminder_status(
            mock_session, uuid4(), ReminderStatus.COMPLETED
        )

        assert result is None


class TestDeleteReminder:
    """Tests for delete_reminder function."""

    @pytest.mark.asyncio
    async def test_delete_success(self, mock_session):
        """Test deleting reminder successfully."""
        from crud.reminder import delete_reminder

        reminder_id = uuid4()
        mock_reminder = MagicMock()
        mock_session.get.return_value = mock_reminder

        result = await delete_reminder(mock_session, reminder_id)

        assert result is True
        mock_session.delete.assert_called_once_with(mock_reminder)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_session):
        """Test deleting nonexistent reminder returns False."""
        from crud.reminder import delete_reminder

        mock_session.get.return_value = None

        result = await delete_reminder(mock_session, uuid4())

        assert result is False
        mock_session.delete.assert_not_called()
