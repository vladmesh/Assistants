# rest_service/tests/unit/test_crud_user.py
"""Unit tests for user CRUD operations.

These tests mock the database session to test business logic without actual DB.
"""

from unittest.mock import AsyncMock, MagicMock, patch

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


class TestGetUserById:
    """Tests for get_user_by_id function."""

    @pytest.mark.asyncio
    async def test_user_found(self, mock_session):
        """Test getting user when exists."""
        from crud.user import get_user_by_id

        # Mock user data
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.telegram_id = 12345
        mock_session.get.return_value = mock_user

        result = await get_user_by_id(mock_session, 1)

        assert result == mock_user
        mock_session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_not_found(self, mock_session):
        """Test getting user when not exists."""
        from crud.user import get_user_by_id

        mock_session.get.return_value = None

        result = await get_user_by_id(mock_session, 999)

        assert result is None


class TestGetUserByTelegramId:
    """Tests for get_user_by_telegram_id function."""

    @pytest.mark.asyncio
    async def test_user_found(self, mock_session):
        """Test getting user by telegram_id when exists."""
        from crud.user import get_user_by_telegram_id

        mock_user = MagicMock()
        mock_user.telegram_id = 12345

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        result = await get_user_by_telegram_id(mock_session, 12345)

        assert result == mock_user
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_not_found(self, mock_session):
        """Test getting user by telegram_id when not exists."""
        from crud.user import get_user_by_telegram_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await get_user_by_telegram_id(mock_session, 99999)

        assert result is None


class TestCreateUser:
    """Tests for create_user function."""

    @pytest.mark.asyncio
    async def test_create_new_user(self, mock_session):
        """Test creating new user successfully."""
        from shared_models.api_schemas import TelegramUserCreate

        from crud.user import create_user

        # No existing user - mock get_user_by_telegram_id returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        user_in = TelegramUserCreate(telegram_id=12345, username="test_user")

        # Patch get_user_by_telegram_id to return None (no existing user)
        with patch(
            "crud.user.get_user_by_telegram_id", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            result = await create_user(mock_session, user_in)

            # Verify user was added and committed
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()
            # Result should be a TelegramUser model
            assert result is not None

    @pytest.mark.asyncio
    async def test_create_duplicate_user_raises(self, mock_session):
        """Test creating user with existing telegram_id raises error."""
        from shared_models.api_schemas import TelegramUserCreate

        from crud.user import create_user

        # Existing user found
        existing_user = MagicMock()
        existing_user.telegram_id = 12345
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_session.execute.return_value = mock_result

        user_in = TelegramUserCreate(telegram_id=12345)

        with pytest.raises(ValueError, match="already exists"):
            await create_user(mock_session, user_in)


class TestUpdateUser:
    """Tests for update_user function."""

    @pytest.mark.asyncio
    async def test_update_existing_user(self, mock_session):
        """Test updating existing user."""
        from shared_models.api_schemas import TelegramUserUpdate

        from crud.user import update_user

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "old_name"
        mock_session.get.return_value = mock_user

        user_update = TelegramUserUpdate(username="new_name")

        result = await update_user(mock_session, 1, user_update)

        assert result == mock_user
        assert mock_user.username == "new_name"
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_nonexistent_user(self, mock_session):
        """Test updating nonexistent user returns None."""
        from shared_models.api_schemas import TelegramUserUpdate

        from crud.user import update_user

        mock_session.get.return_value = None
        user_update = TelegramUserUpdate(username="new_name")

        result = await update_user(mock_session, 999, user_update)

        assert result is None
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_partial(self, mock_session):
        """Test partial update only changes specified fields."""
        from shared_models.api_schemas import TelegramUserUpdate

        from crud.user import update_user

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "old_name"
        mock_user.timezone = "UTC"
        mock_session.get.return_value = mock_user

        # Only update username, leave timezone
        user_update = TelegramUserUpdate(username="new_name")

        await update_user(mock_session, 1, user_update)

        assert mock_user.username == "new_name"
        # timezone should remain unchanged (not in update)


class TestDeleteUser:
    """Tests for delete_user function."""

    @pytest.mark.asyncio
    async def test_delete_existing_user(self, mock_session):
        """Test deleting existing user."""
        from crud.user import delete_user

        mock_user = MagicMock()
        mock_session.get.return_value = mock_user

        result = await delete_user(mock_session, 1)

        assert result is True
        mock_session.delete.assert_called_once_with(mock_user)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_user(self, mock_session):
        """Test deleting nonexistent user returns False."""
        from crud.user import delete_user

        mock_session.get.return_value = None

        result = await delete_user(mock_session, 999)

        assert result is False
        mock_session.delete.assert_not_called()


class TestGetUsers:
    """Tests for get_users function."""

    @pytest.mark.asyncio
    async def test_get_users_list(self, mock_session):
        """Test getting list of users."""
        from crud.user import get_users

        mock_users = [MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_users
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await get_users(mock_session, skip=0, limit=10)

        assert result == mock_users
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_users_empty(self, mock_session):
        """Test getting empty users list."""
        from crud.user import get_users

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await get_users(mock_session)

        assert result == []
