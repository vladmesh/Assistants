"""REST service client for interacting with the REST API"""

import json
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from config.logger import get_logger
from config.settings import settings
from pydantic import BaseModel

# Import Pydantic models used for response parsing
# Use models from shared_models instead of local models.rest
from shared_models import AssistantModel  # Renamed from Assistant
from shared_models import CreateReminderRequest  # Renamed from ReminderCreate
from shared_models import ReminderModel  # Renamed from Reminder
from shared_models import ToolModel  # Renamed from Tool
from shared_models import UserModel  # Renamed from TelegramUser
from shared_models.api_models import UserSecretaryAssignment  # Import the new model

logger = get_logger(__name__)


class User(BaseModel):
    """User model from REST service"""

    id: int
    telegram_id: int
    username: Optional[str] = None


class Assistant(BaseModel):
    """Assistant model from REST service"""

    id: UUID
    name: str
    is_secretary: bool
    model: str
    instructions: str
    assistant_type: str
    openai_assistant_id: Optional[str] = None
    is_active: bool
    tools: List[UUID] = []


class Tool(BaseModel):
    """Tool model from REST service"""

    id: str
    name: str
    description: str
    is_active: bool
    tool_type: str
    input_schema: str  # JSON string
    created_at: str
    updated_at: str
    assistant_id: Optional[str] = None  # ID of sub-assistant for sub_assistant type

    @property
    def input_schema_dict(self) -> Dict[str, Any]:
        """Get input schema as dictionary"""
        return json.loads(self.input_schema)


class UserAssistantThread(BaseModel):
    """User assistant thread model from REST service"""

    id: UUID
    user_id: str
    assistant_id: UUID
    thread_id: str
    last_used: str


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
        self.base_url = (base_url or settings.REST_SERVICE_BASE_URL).rstrip("/")
        self._client = httpx.AsyncClient()
        self._cache: Dict[str, Any] = {}
        logger.info(f"RestServiceClient initialized with base URL: {self.base_url}")

    async def close(self):
        """Close the HTTP client"""
        await self._client.aclose()
        logger.info("RestServiceClient closed.")

    async def get_assistant_tools(self, assistant_id: str) -> List[ToolModel]:
        """Get tools associated with a specific assistant."""
        # Wrap the core logic in try...except to handle errors from _request
        try:
            logger.debug(f"Fetching tools for assistant ID: {assistant_id}")
            # Use the _request helper which handles common HTTP errors
            data = await self._request("GET", f"/api/assistants/{assistant_id}/tools")
            # Ensure data is a list before list comprehension
            if isinstance(data, list):
                # Parse using ToolModel from shared_models
                return [ToolModel(**item) for item in data]
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

    async def get_user(self, user_id: int) -> UserModel:
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
        return UserModel(**data)

    async def _request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """Helper method to make requests and handle common errors."""
        full_url = f"{self.base_url}{endpoint}"  # Construct full URL
        logger.debug(f"Making request: {method} {full_url}")
        try:
            # Use the constructed full_url
            response = await self._client.request(method, full_url, **kwargs)
            response.raise_for_status()  # Raise exception for 4xx or 5xx status codes
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
                f"Failed to decode JSON response",
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

    async def get_user_by_telegram_id(self, telegram_id: str) -> Optional[UserModel]:
        """Get user by Telegram ID."""
        try:
            data = await self._request("GET", f"/api/users/by_telegram/{telegram_id}")
            return UserModel(**data) if data else None
        except RestServiceError as e:
            # Specifically handle 404 as user not found, others re-raise
            if "404" in str(e):
                logger.warning(f"User not found for telegram_id: {telegram_id}")
                return None
            raise  # Re-raise other errors

    async def get_user_secretary(self, user_id: int) -> Optional[AssistantModel]:
        """Get the secretary assistant associated with a user."""
        try:
            data = await self._request("GET", f"/api/users/{user_id}/secretary")
            return AssistantModel(**data) if data else None
        except RestServiceError as e:
            if "404" in str(e):
                logger.warning(f"Secretary not found for user_id: {user_id}")
                return None
            raise

    async def get_assistant(self, assistant_id: str) -> Optional[AssistantModel]:
        """Get assistant details by ID."""
        try:
            data = await self._request("GET", f"/api/assistants/{assistant_id}")
            return AssistantModel(**data) if data else None
        except RestServiceError as e:
            if "404" in str(e):
                logger.warning(f"Assistant not found with id: {assistant_id}")
                return None
            raise

    async def get_assistants(self) -> List[AssistantModel]:
        """Get a list of all assistants."""
        try:
            data = await self._request("GET", "/api/assistants/")
            # Ensure data is a list before list comprehension
            if isinstance(data, list):
                return [AssistantModel(**item) for item in data]
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

    async def get_tools(self) -> List[ToolModel]:
        """Get list of all tools."""
        try:
            data = await self._request("GET", "/api/tools/")
            if isinstance(data, list):
                return [ToolModel(**tool) for tool in data]
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

    async def get_tool(self, tool_id: str) -> Optional[ToolModel]:
        """Get tool by ID."""
        try:
            data = await self._request("GET", f"/api/tools/{tool_id}")
            return ToolModel(**data) if data else None
        except RestServiceError as e:
            if "404" in str(e):
                logger.warning(f"Tool not found with id: {tool_id}")
                return None
            raise
        except Exception:
            logger.exception(f"Unexpected error getting tool {tool_id}", exc_info=True)
            return None

    async def create_reminder(
        self, reminder_data: CreateReminderRequest
    ) -> Optional[ReminderModel]:
        """Create a new reminder."""
        try:
            response_data = await self._request(
                "POST", "/api/reminders/", json=reminder_data.model_dump()
            )
            return ReminderModel(**response_data) if response_data else None
        except RestServiceError as e:  # Changed exception handling
            # Log details if needed, re-raise
            logger.error(
                "Failed to create reminder",
                data=reminder_data.model_dump(),
                error=str(e),
            )
            raise
        except Exception:
            logger.exception(
                "Unexpected error creating reminder",
                data=reminder_data.model_dump(),
                exc_info=True,
            )
            return None  # Return None on unexpected errors

    async def list_active_user_secretary_assignments(
        self,
    ) -> List[UserSecretaryAssignment]:
        """Fetch the list of active user-secretary assignments."""
        # Add the /api prefix to the URL
        response_data = await self._request("GET", "/api/user-secretaries/assignments")
        # _request already returns decoded JSON (list in this case)
        if isinstance(response_data, list):
            return [
                UserSecretaryAssignment(**assignment) for assignment in response_data
            ]
        else:
            logger.error(
                f"Expected list from /api/user-secretaries/assignments, got {type(response_data)}"
            )
            return []  # Return empty list on unexpected type
