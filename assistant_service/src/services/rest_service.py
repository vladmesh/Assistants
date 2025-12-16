"""REST service client for interacting with the REST API using BaseServiceClient."""

from typing import Any
from uuid import UUID

from shared_models import (
    BaseServiceClient,
    ClientConfig,
    ServiceClientError,
    ServiceResponseError,
    get_logger,
)
from shared_models.api_schemas import (
    AssistantRead,
    GlobalSettingsBase,
    ReminderCreate,
    ReminderRead,
    TelegramUserRead,
    ToolRead,
    UserSecretaryLinkRead,
)
from shared_models.api_schemas.message import MessageCreate, MessageRead, MessageUpdate

from config.settings import settings

logger = get_logger(__name__)


# Alias for backward compatibility
RestServiceError = ServiceClientError


class RestServiceClient(BaseServiceClient):
    """Client for interacting with the REST service using BaseServiceClient."""

    def __init__(self, base_url: str | None = None):
        """Initialize the client.

        Args:
            base_url: Optional base URL of the REST service.
        """
        config = ClientConfig(
            timeout=settings.HTTP_CLIENT_TIMEOUT,
            connect_timeout=5.0,
            max_retries=3,
            retry_min_wait=1.0,
            retry_max_wait=10.0,
            circuit_breaker_fail_max=5,
            circuit_breaker_reset_timeout=30.0,
        )
        super().__init__(
            base_url=base_url or settings.REST_SERVICE_URL,
            service_name="assistant_service",
            target_service="rest_service",
            config=config,
        )

    async def get_assistant_tools(self, assistant_id: str) -> list[ToolRead]:
        """Get tools associated with a specific assistant."""
        try:
            data = await self.request("GET", f"/api/assistants/{assistant_id}/tools")
            if isinstance(data, list):
                return [ToolRead(**item) for item in data]
            logger.error(
                "Unexpected data format for assistant tools",
                assistant_id=assistant_id,
                data_received=data,
            )
            return []
        except ServiceResponseError as e:
            if e.status_code == 404:
                logger.warning(f"Assistant or tools not found for ID: {assistant_id}")
                return []
            logger.error(f"Failed to get tools for assistant {assistant_id}: {e}")
            return []
        except Exception:
            logger.exception(
                f"Unexpected error getting tools for assistant {assistant_id}"
            )
            return []

    async def get_user(self, user_id: int) -> TelegramUserRead:
        """Get user by ID.

        Args:
            user_id: User ID (not telegram_id)

        Returns:
            TelegramUserRead object

        Raises:
            ServiceClientError: If request fails
        """
        data = await self.request("GET", f"/api/users/{user_id}")
        return TelegramUserRead(**data)

    async def get_user_by_telegram_id(
        self, telegram_id: str
    ) -> TelegramUserRead | None:
        """Get user by Telegram ID."""
        try:
            data = await self.request("GET", f"/api/users/by_telegram/{telegram_id}")
            return TelegramUserRead(**data) if data else None
        except ServiceResponseError as e:
            if e.status_code == 404:
                logger.warning(f"User not found for telegram_id: {telegram_id}")
                return None
            raise

    async def get_user_secretary(self, user_id: int) -> AssistantRead | None:
        """Get the secretary assistant associated with a user."""
        try:
            data = await self.request("GET", f"/api/users/{user_id}/secretary")
            return AssistantRead(**data) if data else None
        except ServiceResponseError as e:
            if e.status_code == 404:
                logger.warning(f"Secretary not found for user_id: {user_id}")
                return None
            raise

    async def get_assistant(self, assistant_id: str) -> AssistantRead | None:
        """Get assistant details by ID."""
        try:
            data = await self.request("GET", f"/api/assistants/{assistant_id}")
            return AssistantRead(**data) if data else None
        except ServiceResponseError as e:
            if e.status_code == 404:
                logger.warning(f"Assistant not found with id: {assistant_id}")
                return None
            raise

    async def get_assistants(self) -> list[AssistantRead]:
        """Get a list of all assistants."""
        try:
            data = await self.request("GET", "/api/assistants/")
            if isinstance(data, list):
                return [AssistantRead(**item) for item in data]
            logger.error(
                f"Received unexpected data type for assistants list: {type(data)}"
            )
            return []
        except ServiceClientError as e:
            logger.error(f"Failed to get assistants list: {e}")
            raise
        except Exception:
            logger.exception("Unexpected error getting assistants list")
            return []

    async def get_tools(self) -> list[ToolRead]:
        """Get list of all tools."""
        try:
            data = await self.request("GET", "/api/tools/")
            if isinstance(data, list):
                return [ToolRead(**tool) for tool in data]
            logger.error(f"Received unexpected data type for tools list: {type(data)}")
            return []
        except ServiceClientError as e:
            logger.error(f"Failed to get tools list: {e}")
            raise
        except Exception:
            logger.exception("Unexpected error getting tools list")
            return []

    async def get_tool(self, tool_id: str) -> ToolRead | None:
        """Get tool by ID."""
        try:
            data = await self.request("GET", f"/api/tools/{tool_id}")
            return ToolRead(**data) if data else None
        except ServiceResponseError as e:
            if e.status_code == 404:
                logger.warning(f"Tool not found with id: {tool_id}")
                return None
            raise
        except Exception:
            logger.exception(f"Unexpected error getting tool {tool_id}")
            return None

    async def create_reminder(
        self, reminder_data: ReminderCreate
    ) -> ReminderRead | None:
        """Create a new reminder.

        Args:
            reminder_data: Reminder creation data.

        Returns:
            ReminderRead object if successful, None otherwise.
        """
        try:
            response_data = await self.request(
                "POST", "/api/reminders/", json=reminder_data.model_dump(mode="json")
            )
            if response_data:
                return ReminderRead(**response_data)
            return None
        except ServiceClientError as e:
            logger.error(
                f"Failed to create reminder for user {reminder_data.user_id}: {e}"
            )
            return None
        except Exception:
            logger.exception(
                f"Unexpected error creating reminder for user {reminder_data.user_id}"
            )
            return None

    async def get_user_active_reminders(self, user_id: int) -> list[ReminderRead]:
        """Get a list of active reminders for a specific user.

        Args:
            user_id: The ID of the user.

        Returns:
            A list of ReminderRead objects.
        """
        try:
            response_data = await self.request(
                "GET", f"/api/reminders/user/{user_id}", params={"status": "active"}
            )
            if isinstance(response_data, list):
                return [ReminderRead(**item) for item in response_data]
            logger.error(
                "Unexpected format for user active reminders",
                user_id=user_id,
                data_received=response_data,
            )
            return []
        except ServiceClientError as e:
            logger.error(f"Failed to get active reminders for user {user_id}: {e}")
            return []
        except Exception:
            logger.exception(
                f"Unexpected error getting active reminders for user {user_id}"
            )
            return []

    async def delete_reminder(self, reminder_id: UUID) -> bool:
        """Delete a reminder by its ID.

        Args:
            reminder_id: The UUID of the reminder to delete.

        Returns:
            True if deletion was successful, False otherwise.
        """
        try:
            await self.request("DELETE", f"/api/reminders/{str(reminder_id)}")
            logger.info(f"Successfully deleted reminder {reminder_id}")
            return True
        except ServiceClientError as e:
            logger.error(f"Failed to delete reminder {reminder_id}: {e}")
            return False
        except Exception:
            logger.exception(f"Unexpected error deleting reminder {reminder_id}")
            return False

    async def list_active_user_secretary_assignments(
        self,
    ) -> list[UserSecretaryLinkRead]:
        """Fetch the list of active user-secretary assignments."""
        response_data = await self.request("GET", "/api/user-secretaries/assignments")
        if isinstance(response_data, list):
            return [UserSecretaryLinkRead(**assignment) for assignment in response_data]
        logger.error(
            "Expected list from /api/user-secretaries/assignments, "
            f"got {type(response_data)}"
        )
        return []

    async def get_user_secretary_assignment(self, user_id: int) -> dict | None:
        """Fetch the active secretary assignment for a specific user."""
        endpoint = f"/api/users/{user_id}/secretary"
        try:
            response_data = await self.request("GET", endpoint)
            if response_data:
                logger.info(
                    "Found secretary assignment for user",
                    user_id=user_id,
                    secretary_id=response_data.get("id"),
                )
                return response_data
            logger.info(
                "No active secretary assignment found for user via REST",
                user_id=user_id,
            )
            return None
        except ServiceResponseError as e:
            if e.status_code == 404:
                logger.info(
                    "No active secretary assignment found for user via REST",
                    user_id=user_id,
                )
                return None
            logger.error(f"Error fetching secretary assignment for user {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching secretary assignment for user {user_id}: {e}")
            return None

    async def get_active_assignments(self) -> list[dict]:
        """Fetch all active user-secretary assignments."""
        data = await self.request("GET", "/api/user-secretaries/assignments")
        return data if isinstance(data, list) else []

    # Message handling methods

    async def create_message(self, message_data: MessageCreate) -> MessageRead | None:
        """Creates a new message in the database.

        Args:
            message_data: The message data to create

        Returns:
            The created message if successful, None otherwise
        """
        try:
            data = await self.request(
                "POST",
                "/api/messages/",
                json=message_data.model_dump(mode="json", exclude_unset=True),
            )
            if not data:
                logger.warning("Empty response when creating message")
                return None
            return MessageRead(**data)
        except ServiceClientError as e:
            logger.error(f"Error creating message: {e}")
            return None

    async def get_message(self, message_id: int) -> MessageRead | None:
        """Gets a message by ID.

        Args:
            message_id: The message ID

        Returns:
            The message if found, None otherwise
        """
        try:
            data = await self.request("GET", f"/api/messages/{message_id}")
            if not data:
                logger.info(f"No message found with ID {message_id}")
                return None
            return MessageRead(**data)
        except ServiceResponseError as e:
            if e.status_code == 404:
                logger.info(f"No message found with ID {message_id}")
                return None
            logger.warning(f"Error getting message {message_id}: {e}")
            return None
        except ServiceClientError as e:
            logger.warning(f"Error getting message {message_id}: {e}")
            return None

    async def get_messages(
        self,
        user_id: int | None = None,
        assistant_id: str | None = None,
        id_gt: int | None = None,
        id_lt: int | None = None,
        role: str | None = None,
        status: str | None = None,
        summary_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "id",
        sort_order: str = "desc",
    ) -> list[MessageRead]:
        """Gets messages with filtering, sorting, and pagination.

        Args:
            user_id: Filter by user ID
            assistant_id: Filter by assistant ID
            id_gt: Filter for IDs greater than this value
            id_lt: Filter for IDs less than this value
            role: Filter by role (e.g., 'user', 'assistant')
            status: Filter by status (e.g., 'pending_processing', 'processed')
            summary_id: Filter by summary ID
            limit: Maximum number of results to return
            offset: Number of results to skip
            sort_by: Field to sort by ('id' or 'timestamp')
            sort_order: Sort order ('asc' or 'desc')

        Returns:
            List of messages matching the criteria
        """
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }

        if user_id is not None:
            params["user_id"] = user_id
        if assistant_id is not None:
            params["assistant_id"] = assistant_id
        if id_gt is not None:
            params["id_gt"] = id_gt
        if id_lt is not None:
            params["id_lt"] = id_lt
        if role is not None:
            params["role"] = role
        if status is not None:
            params["status"] = status
        if summary_id is not None:
            params["summary_id"] = summary_id

        try:
            data = await self.request("GET", "/api/messages/", params=params)
            if not isinstance(data, list):
                logger.error(f"Unexpected response format for messages: {type(data)}")
                return []
            return [MessageRead(**item) for item in data]
        except ServiceClientError as e:
            logger.error(f"Error getting messages: {e}")
            return []

    async def update_message(
        self, message_id: int, update_data: MessageUpdate
    ) -> MessageRead | None:
        """Updates a message by ID.

        Args:
            message_id: The message ID to update
            update_data: The update data

        Returns:
            The updated message if successful, None otherwise
        """
        try:
            data = await self.request(
                "PATCH",
                f"/api/messages/{message_id}",
                json=update_data.model_dump(exclude_unset=True, mode="json"),
            )
            if not data:
                logger.warning(f"Empty response when updating message {message_id}")
                return None
            return MessageRead(**data)
        except ServiceClientError as e:
            logger.error(f"Error updating message {message_id}: {e}")
            return None

    # --- Global Settings --- #

    async def get_global_settings(self) -> GlobalSettingsBase:
        """Get global settings from REST service."""
        try:
            response = await self.request("GET", "/api/global-settings/")
            if response:
                return GlobalSettingsBase(**response)
            logger.error("Failed to get global settings: empty response")
            raise ValueError("Failed to retrieve global settings: empty response")
        except Exception as e:
            logger.error(f"Error getting global settings: {e}")
            raise ValueError(f"Failed to retrieve global settings: {e}") from e

    async def close_session(self):
        """Alias for close to maintain compatibility."""
        await self.close()
