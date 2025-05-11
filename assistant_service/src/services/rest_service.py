"""REST service client for interacting with the REST API"""

import json
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from config.logger import get_logger
from config.settings import settings
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Import Pydantic models used for response parsing
# Use schemas from shared_models.api_schemas instead of old models
from shared_models.api_schemas import (
    AssistantRead,
    GlobalSettingsRead,
    GlobalSettingsUpdate,
    ReminderCreate,
    ReminderRead,
    TelegramUserRead,
    ToolRead,
    UserSecretaryLinkRead,
    UserSummaryCreateUpdate,
    UserSummaryRead,
)

# Import new message models
from shared_models.api_schemas.message import MessageCreate, MessageRead, MessageUpdate
from shared_models.api_schemas.user_fact import UserFactRead

logger = get_logger(__name__)


class RestServiceError(Exception):
    """Custom exception for REST service client errors."""


class RestServiceClient:
    """Client for interacting with the REST service"""

    def __init__(self, base_url: Optional[str] = None):
        """Initialize the client

        Args:
            base_url: Optional base URL of the REST service.
                If not provided, uses settings.
        """
        self.base_url = (base_url or settings.REST_SERVICE_URL).rstrip("/")
        # Initialize AsyncClient with timeout from settings
        timeout = httpx.Timeout(
            settings.HTTP_CLIENT_TIMEOUT, connect=5.0
        )  # Use configured timeout, add connect timeout
        self._client = httpx.AsyncClient(timeout=timeout)
        self._cache: Dict[str, Any] = {}
        logger.info(f"RestServiceClient initialized with base URL: {self.base_url}")

    async def close(self):
        """Close the HTTP client"""
        await self._client.aclose()
        logger.info("RestServiceClient closed.")

    async def get_assistant_tools(self, assistant_id: str) -> List[ToolRead]:
        """Get tools associated with a specific assistant."""
        # Wrap the core logic in try...except to handle errors from _request
        try:
            # Use the _request helper which handles common HTTP errors
            data = await self._request("GET", f"/api/assistants/{assistant_id}/tools")
            # Ensure data is a list before list comprehension
            if isinstance(data, list):
                # Parse using ToolRead from shared_models.api_schemas
                return [ToolRead(**item) for item in data]
            else:
                logger.error(
                    f"Received unexpected data format for assistant tools: {type(data)}",
                    assistant_id=assistant_id,
                    data_received=data,
                )
                return []  # Return empty list if data format is wrong
        except RestServiceError as e:
            # Log the specific error for this operation
            logger.error(
                f"Failed to get tools for assistant {assistant_id}: {e}", exc_info=True
            )
            # Handle 404 specifically if needed, otherwise return empty list or re-raise
            if "404" in str(e):  # Simple check, might need refinement
                logger.warning(f"Assistant or tools not found for ID: {assistant_id}")
                return []  # Return empty list if assistant not found
            # For other errors, returning empty list might mask issues, consider re-raising
            # raise e # Option to re-raise other errors
            return []  # Defaulting to empty list for now
        except Exception:
            # Catch any other unexpected errors during processing
            logger.exception(
                f"Unexpected error getting tools for assistant {assistant_id}",
                exc_info=True,
            )
            return []  # Return empty list on unexpected errors

    async def get_user_assistant_thread(
        self, user_id: str, assistant_id: UUID
    ) -> Optional[Any]:
        """Get thread for user-assistant pair

        Args:
            user_id: User ID
            assistant_id: Assistant ID

        Returns:
            UserAssistantThread object if found, None otherwise
        """
        try:
            # Use _request helper
            data = await self._request(
                "GET", f"/api/users/{user_id}/assistants/{assistant_id}/thread"
            )
            return data  # Return raw dict for now
        except RestServiceError as e:
            if "404" in str(e):
                logger.warning(
                    f"Thread not found for user {user_id}, assistant {assistant_id}"
                )
                return None
            raise

    async def create_user_assistant_thread(
        self, user_id: str, assistant_id: UUID, thread_id: str
    ) -> Any:
        """Create or update thread for user-assistant pair

        Args:
            user_id: User ID
            assistant_id: Assistant ID
            thread_id: OpenAI thread ID

        Returns:
            Created/updated UserAssistantThread object
        """
        # Use _request helper
        data = await self._request(
            "POST",
            f"/api/users/{user_id}/assistants/{assistant_id}/thread",
            json={"thread_id": thread_id},
        )
        return data  # Return raw dict for now

    async def get_user(self, user_id: int) -> TelegramUserRead:
        """Get user by ID

        Args:
            user_id: User ID (not telegram_id)

        Returns:
            UserModel object

        Raises:
            RestServiceError: If request fails
        """
        # Use _request helper
        data = await self._request("GET", f"/api/users/{user_id}")
        return TelegramUserRead(**data)

    @retry(
        stop=stop_after_attempt(3),  # Retry up to 3 times
        wait=wait_exponential(
            multiplier=1, min=1, max=10
        ),  # Exponential backoff (1s, 2s, 4s ...)
        retry=retry_if_exception_type(
            (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.NetworkError,
                httpx.HTTPStatusError,  # Add HTTPStatusError to potentially retry on 5xx
            )
        ),
        reraise=True,  # Re-raise the exception after retries are exhausted
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying request {retry_state.args[1]} {retry_state.args[2]} due to {retry_state.outcome.exception()}, attempt {retry_state.attempt_number}"
        ),  # Log before sleep
    )
    async def _request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """Helper method to make requests and handle common errors with retries."""
        full_url = f"{self.base_url}{endpoint}"  # Construct full URL
        try:
            # Use the constructed full_url
            response = await self._client.request(method, full_url, **kwargs)

            # Check for specific 5xx errors to retry, raise others immediately
            if 500 <= response.status_code < 600:
                logger.warning(
                    f"Received server error {response.status_code} for {method} {full_url}"
                )
                response.raise_for_status()  # Will be caught by tenacity if it's HTTPStatusError
            elif response.status_code >= 400:
                # Don't retry client errors (4xx), raise immediately
                logger.error(
                    f"Client error {response.status_code} for {method} {full_url}. Not retrying."
                )
                response.raise_for_status()  # Raise HTTPStatusError for non-retryable 4xx

            # Handle potential empty response for non-GET requests or 204
            if response.status_code == 204:
                return {}  # Return empty dict for No Content
            # Check if response has content before trying to decode JSON
            if response.headers.get("content-length") == "0" or not response.content:
                return {}  # Return empty dict if no content
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error occurred: {e.response.status_code} - {e.response.text}",
                method=method,
                url=full_url,  # Log full_url
                response_body=e.response.text,
                exc_info=True,  # Add exc_info for better debugging
            )
            # Try to parse error detail from response
            error_detail = "Unknown error"
            try:
                error_data = e.response.json()
                if isinstance(error_data, dict) and "detail" in error_data:
                    error_detail = error_data["detail"]
            except json.JSONDecodeError:
                error_detail = e.response.text  # Use raw text if not JSON

            raise RestServiceError(
                f"HTTP {e.response.status_code} error for {method} {full_url}: {error_detail}"  # Use full_url
            ) from e
        except httpx.RequestError as e:
            logger.error(
                f"Request error occurred: {e}",
                method=method,
                url=full_url,  # Log full_url
                exc_info=True,  # Add exc_info for better debugging
            )
            # Check for specific error types like UnsupportedProtocol
            if isinstance(e, httpx.UnsupportedProtocol):
                logger.error(
                    f"UnsupportedProtocol error likely due to missing schema in base URL or endpoint: {full_url}",
                    method=method,
                )
                raise RestServiceError(
                    f"Request URL is missing schema for {method} {full_url}"
                ) from e
            raise RestServiceError(
                f"Request error for {method} {full_url}: {e}"
            ) from e  # Use full_url
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to decode JSON response",
                method=method,
                url=full_url,  # Log full_url
                response_status=response.status_code
                if "response" in locals()
                else "N/A",
                response_text=response.text if "response" in locals() else "N/A",
            )
            raise RestServiceError(
                f"Failed to decode JSON response for {method} {full_url}"  # Use full_url
            ) from e

    async def get_user_by_telegram_id(
        self, telegram_id: str
    ) -> Optional[TelegramUserRead]:
        """Get user by Telegram ID."""
        try:
            data = await self._request("GET", f"/api/users/by_telegram/{telegram_id}")
            return TelegramUserRead(**data) if data else None
        except RestServiceError as e:
            # Specifically handle 404 as user not found, others re-raise
            if "404" in str(e):
                logger.warning(f"User not found for telegram_id: {telegram_id}")
                return None
            raise  # Re-raise other errors

    async def get_user_secretary(self, user_id: int) -> Optional[AssistantRead]:
        """Get the secretary assistant associated with a user."""
        try:
            data = await self._request("GET", f"/api/users/{user_id}/secretary")
            return AssistantRead(**data) if data else None
        except RestServiceError as e:
            if "404" in str(e):
                logger.warning(f"Secretary not found for user_id: {user_id}")
                return None
            raise

    async def get_assistant(self, assistant_id: str) -> Optional[AssistantRead]:
        """Get assistant details by ID."""
        try:
            data = await self._request("GET", f"/api/assistants/{assistant_id}")
            return AssistantRead(**data) if data else None
        except RestServiceError as e:
            if "404" in str(e):
                logger.warning(f"Assistant not found with id: {assistant_id}")
                return None
            raise

    async def get_assistants(self) -> List[AssistantRead]:
        """Get a list of all assistants."""
        try:
            data = await self._request("GET", "/api/assistants/")
            # Ensure data is a list before list comprehension
            if isinstance(data, list):
                return [AssistantRead(**item) for item in data]
            else:
                logger.error(
                    f"Received unexpected data type for assistants list: {type(data)}"
                )
                return []
        except RestServiceError as e:  # Added specific handling
            logger.error(f"Failed to get assistants list: {e}", exc_info=True)
            raise  # Re-raise error after logging
        except Exception:
            logger.exception("Unexpected error getting assistants list", exc_info=True)
            return []  # Return empty list on unexpected errors

    async def get_tools(self) -> List[ToolRead]:
        """Get list of all tools."""
        try:
            data = await self._request("GET", "/api/tools/")
            if isinstance(data, list):
                return [ToolRead(**tool) for tool in data]
            else:
                logger.error(
                    f"Received unexpected data type for tools list: {type(data)}"
                )
                return []
        except RestServiceError as e:
            logger.error(f"Failed to get tools list: {e}", exc_info=True)
            raise
        except Exception:
            logger.exception("Unexpected error getting tools list", exc_info=True)
            return []

    async def get_tool(self, tool_id: str) -> Optional[ToolRead]:
        """Get tool by ID."""
        try:
            data = await self._request("GET", f"/api/tools/{tool_id}")
            return ToolRead(**data) if data else None
        except RestServiceError as e:
            if "404" in str(e):
                logger.warning(f"Tool not found with id: {tool_id}")
                return None
            raise
        except Exception:
            logger.exception(f"Unexpected error getting tool {tool_id}", exc_info=True)
            return None

    async def create_reminder(
        self, reminder_data: ReminderCreate
    ) -> Optional[ReminderRead]:
        """Create a new reminder.

        Args:
            reminder_data: Reminder creation data.

        Returns:
            ReminderRead object if successful, None otherwise.
        """
        try:
            response_data = await self._request(
                "POST", "/api/reminders/", json=reminder_data.model_dump(mode="json")
            )
            if response_data:
                return ReminderRead(**response_data)
            return None  # Should not happen if API returns 201 with body
        except RestServiceError as e:
            logger.error(
                f"Failed to create reminder for user {reminder_data.user_id}: {e}",
                exc_info=True,
            )
            return None
        except Exception:
            logger.exception(
                f"Unexpected error creating reminder for user {reminder_data.user_id}",
                exc_info=True,
            )
            return None

    async def get_user_active_reminders(self, user_id: int) -> List[ReminderRead]:
        """Get a list of active reminders for a specific user.

        Args:
            user_id: The ID of the user.

        Returns:
            A list of ReminderRead objects.
        """
        try:
            # GET /api/reminders/user/{user_id}?status=active
            response_data = await self._request(
                "GET", f"/api/reminders/user/{user_id}", params={"status": "active"}
            )
            if isinstance(response_data, list):
                return [ReminderRead(**item) for item in response_data]
            logger.error(
                f"Received unexpected data format for user active reminders: {type(response_data)}",
                user_id=user_id,
                data_received=response_data,
            )
            return []
        except RestServiceError as e:
            logger.error(
                f"Failed to get active reminders for user {user_id}: {e}", exc_info=True
            )
            return []
        except Exception:
            logger.exception(
                f"Unexpected error getting active reminders for user {user_id}",
                exc_info=True,
            )
            return []

    async def delete_reminder(self, reminder_id: UUID) -> bool:
        """Delete a reminder by its ID.

        Args:
            reminder_id: The UUID of the reminder to delete.

        Returns:
            True if deletion was successful (e.g., 204 No Content), False otherwise.
        """
        try:
            # DELETE /api/reminders/{reminder_id}
            # _request returns empty dict for 204, or raises error for others
            await self._request("DELETE", f"/api/reminders/{str(reminder_id)}")
            logger.info(f"Successfully deleted reminder {reminder_id}")
            return True
        except RestServiceError as e:
            # Log specific error, but return False as per method contract for failure
            logger.error(f"Failed to delete reminder {reminder_id}: {e}", exc_info=True)
            # Distinguish 404 (not found, arguably a "successful" deletion if goal is absence)
            # from other errors. For now, any RestServiceError means False.
            # if "404" in str(e):
            #     logger.warning(f"Reminder {reminder_id} not found for deletion.")
            #     return True # Or False, depending on desired semantics for "not found"
            return False
        except Exception:
            logger.exception(
                f"Unexpected error deleting reminder {reminder_id}", exc_info=True
            )
            return False

    async def list_active_user_secretary_assignments(
        self,
    ) -> List[UserSecretaryLinkRead]:
        """Fetch the list of active user-secretary assignments."""
        # Add the /api prefix to the URL
        response_data = await self._request("GET", "/api/user-secretaries/assignments")
        # _request already returns decoded JSON (list in this case)
        if isinstance(response_data, list):
            # Parse using UserSecretaryLinkRead
            return [UserSecretaryLinkRead(**assignment) for assignment in response_data]
        else:
            logger.error(
                f"Expected list from /api/user-secretaries/assignments, got {type(response_data)}"
            )
            return []  # Return empty list on unexpected type

    async def get_user_secretary_assignment(self, user_id: int) -> Optional[dict]:
        """Fetch the active secretary assignment for a specific user."""
        endpoint = f"/api/users/{user_id}/secretary"
        try:
            response_data = await self._request("GET", endpoint)
            if response_data:
                logger.info(
                    "Found secretary assignment for user",
                    user_id=user_id,
                    secretary_id=response_data.get("id"),
                )
                # We might need to return the link object containing the update time later for caching
                # For now, just returning the secretary data itself.
                # The endpoint /users/{user_id}/secretary returns the Assistant object directly.
                return response_data
            else:
                # Handle case where _request returns None (e.g., 404)
                logger.info(
                    "No active secretary assignment found for user via REST",
                    user_id=user_id,
                )
                return None
        except Exception as e:
            logger.error(
                f"Error fetching secretary assignment for user {user_id}: {e}",
                exc_info=True,
            )
            return None

    async def get_active_assignments(self) -> List[dict]:
        """Fetch all active user-secretary assignments."""
        f"{self.base_url}/api/user-secretaries/assignments"

    async def get_user_facts(self, user_id: int) -> List[UserFactRead]:
        """Get facts for a specific user.

        Args:
            user_id: The ID of the user.

        Returns:
            A list of fact strings.

        Raises:
            RestServiceError: If the request fails or returns unexpected data.
        """
        try:
            # Use the _request helper
            data = await self._request("GET", f"/api/users/{user_id}/facts")

            # Ensure data is a list before processing
            if isinstance(data, list):
                # Parse each item using UserFactRead and extract the 'fact' string
                facts_list: List[UserFactRead] = [UserFactRead(**item) for item in data]
                fact_strings: List[str] = [fact_obj.fact for fact_obj in facts_list]
                logger.debug(
                    f"Successfully parsed {len(fact_strings)} facts for user {user_id}."
                )
                return facts_list
            else:
                logger.error(
                    f"Received unexpected data format for user facts: {type(data)}",
                    user_id=user_id,
                    data_received=data,
                )
                # Raise an error or return empty list? Raising for clarity.
                raise RestServiceError(
                    f"Unexpected data format received for user facts: {type(data)}"
                )

        except RestServiceError as e:
            # Log the specific error for this operation
            logger.error(f"Failed to get facts for user {user_id}: {e}", exc_info=True)
            # Handle 404 specifically if needed (user not found or no facts)
            if "404" in str(e):
                logger.warning(f"User {user_id} not found or has no facts.")
                return []  # Return empty list if user/facts not found
            # For other errors, re-raise to indicate a problem
            raise e
        except Exception as e:
            # Catch any other unexpected errors during processing/parsing
            logger.exception(
                f"Unexpected error getting facts for user {user_id}: {e}",
                exc_info=True,
            )
            raise RestServiceError(
                f"Unexpected error processing facts for user {user_id}"
            ) from e

    async def get_user_summary(
        self, user_id: int, secretary_id: UUID
    ) -> Optional[UserSummaryRead]:
        """Gets the latest summary for a user-secretary pair from the API.

        Args:
            user_id: The user ID
            secretary_id: The secretary ID

        Returns:
            The summary if found, None otherwise
        """
        # Format the secretary_id if it's a UUID object
        try:
            secretary_id_str = str(secretary_id)
        except Exception as e:
            logger.error(f"Invalid secretary_id format: {e}")
            return None

        try:
            data = await self._request(
                "GET",
                f"/api/user-summaries/latest/",
                params={"user_id": user_id, "assistant_id": secretary_id_str},
            )
            # Check if data is empty
            if not data:
                logger.info(
                    f"No summary found for user {user_id}, secretary {secretary_id_str}"
                )
                return None
            return UserSummaryRead(**data)  # Parse as Pydantic model
        except RestServiceError as e:
            logger.warning(
                f"Error getting user summary for {user_id}, {secretary_id_str}: {e}"
            )
            return None

    async def create_user_summary(
        self, summary_data: UserSummaryCreateUpdate
    ) -> Optional[UserSummaryRead]:
        """Creates a new user summary.

        Args:
            summary_data: The summary data to create

        Returns:
            The created summary if successful, None otherwise
        """
        try:
            data = await self._request(
                "POST",
                "/api/user-summaries/",
                json=summary_data.model_dump(exclude_unset=True, mode="json"),
            )
            if not data:
                logger.warning("Empty response when creating user summary")
                return None
            return UserSummaryRead(**data)
        except RestServiceError as e:
            logger.error(f"Error creating user summary: {e}")
            return None

    # New methods for message handling

    async def create_message(
        self, message_data: MessageCreate
    ) -> Optional[MessageRead]:
        """Creates a new message in the database.

        Args:
            message_data: The message data to create

        Returns:
            The created message if successful, None otherwise
        """
        try:
            data = await self._request(
                "POST",
                "/api/messages/",
                json=message_data.model_dump(mode="json", exclude_unset=True),
            )
            if not data:
                logger.warning("Empty response when creating message")
                return None
            return MessageRead(**data)
        except RestServiceError as e:
            logger.error(f"Error creating message: {e}")
            return None

    async def get_message(self, message_id: int) -> Optional[MessageRead]:
        """Gets a message by ID.

        Args:
            message_id: The message ID

        Returns:
            The message if found, None otherwise
        """
        try:
            data = await self._request("GET", f"/api/messages/{message_id}")
            if not data:
                logger.info(f"No message found with ID {message_id}")
                return None
            return MessageRead(**data)
        except RestServiceError as e:
            logger.warning(f"Error getting message {message_id}: {e}")
            return None

    async def get_messages(
        self,
        user_id: Optional[int] = None,
        assistant_id: Optional[str] = None,
        id_gt: Optional[int] = None,
        id_lt: Optional[int] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
        summary_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "id",
        sort_order: str = "desc",
    ) -> List[MessageRead]:
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

        params = {
            "limit": limit,
            "offset": offset,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }

        # Add optional filters if provided
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
            data = await self._request("GET", "/api/messages/", params=params)
            if not isinstance(data, list):
                logger.error(f"Unexpected response format for messages: {type(data)}")
                return []

            result = [MessageRead(**item) for item in data]

            return result
        except RestServiceError as e:
            logger.error(f"Error getting messages: {e}")
            return []

    async def update_message(
        self, message_id: int, update_data: MessageUpdate
    ) -> Optional[MessageRead]:
        """Updates a message by ID.

        Args:
            message_id: The message ID to update
            update_data: The update data

        Returns:
            The updated message if successful, None otherwise
        """
        try:
            data = await self._request(
                "PATCH",
                f"/api/messages/{message_id}",
                json=update_data.model_dump(exclude_unset=True, mode="json"),
            )
            if not data:
                logger.warning(f"Empty response when updating message {message_id}")
                return None
            return MessageRead(**data)
        except RestServiceError as e:
            logger.error(f"Error updating message {message_id}: {e}")
            return None

    # --- Global Settings --- #

    async def get_global_settings(self) -> "GlobalSettingsBase":
        """Get global settings from REST service.

        Returns:
            GlobalSettingsBase: Object with global settings like context_window_size and summarization_prompt
        """
        try:
            response = await self._request("GET", "/api/global-settings/")
            # Ответ уже десериализован, так как _request возвращает словарь, а не Response объект
            if response:
                from shared_models.api_schemas.global_settings import GlobalSettingsBase

                return GlobalSettingsBase(**response)
            else:
                logger.error("Failed to get global settings: empty response")
                # Не возвращаем значения по умолчанию - пусть падает
                raise ValueError("Failed to retrieve global settings: empty response")
        except Exception as e:
            logger.error(f"Error getting global settings: {e}", exc_info=True)
            # Не маскируем ошибку возвращением дефолтных значений, проксируем исключение дальше
            raise ValueError(f"Failed to retrieve global settings: {e}") from e

    # async def update_global_settings(
    #     self, data: GlobalSettingsUpdate
    # ) -> Optional[GlobalSettingsRead]:
    #     """Update the global system settings.

    #     Args:
    #         data: GlobalSettingsUpdate object with fields to update.

    #     Returns:
    #         Updated GlobalSettingsRead object.

    #     Raises:
    #         RestServiceError: If the request fails.
    #     """
    #     updated_data = await self._request(
    #         "PUT",
    #         "/api/global-settings/",
    #         json=data.model_dump(
    #             exclude_unset=True
    #         ),  # Use model_dump and exclude_unset
    #     )
    #     if updated_data:
    #         return GlobalSettingsRead(**updated_data)
    #     return None  # Should indicate an error if PUT succeeded but returned nothing

    async def close_session(self):
        """Alias for close to maintain compatibility if needed"""
        await self.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_session()
