from typing import Dict, Optional
from uuid import UUID

# Project imports
from config.logger import get_logger
from config.settings import Settings

# Langchain imports
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from services.rest_service import RestServiceClient

# Import ToolFactory
from tools.factory import ToolFactory

from .base_assistant import BaseAssistant
from .langgraph_assistant import LangGraphAssistant

logger = get_logger(__name__)


class AssistantFactory:
    def __init__(
        self, settings: Settings, checkpointer: Optional[BaseCheckpointSaver] = None
    ):
        """Initialize the factory with settings, REST client, and checkpointer"""
        self.settings = settings
        self.rest_client = RestServiceClient()
        self._secretary_cache: Dict[int, BaseAssistant] = {}
        self._assistant_cache: Dict[UUID, BaseAssistant] = {}
        self.checkpointer = checkpointer or MemorySaver()
        # Initialize ToolFactory
        self.tool_factory = ToolFactory(settings=self.settings)
        logger.info(
            f"AssistantFactory initialized with checkpointer: {type(self.checkpointer).__name__}"
            f" and ToolFactory"
        )

    async def close(self):
        """Close REST client connection and all assistant instances"""
        await self.rest_client.close()

        # Close all assistant instances
        for assistant in self._secretary_cache.values():
            if hasattr(assistant, "close"):
                await assistant.close()

        self._secretary_cache.clear()

    async def get_user_secretary(self, user_id: int) -> BaseAssistant:
        """Get or create secretary assistant for user.

        Args:
            user_id: Telegram user ID

        Returns:
            Secretary assistant instance

        Raises:
            ValueError: If secretary not found for user
        """
        # Check cache first
        if user_id in self._secretary_cache:
            return self._secretary_cache[user_id]

        # Get user's secretary from REST service
        try:
            secretary = await self.rest_client.get_user_secretary(user_id)
        except Exception as e:
            logger.error("Failed to get user secretary", user_id=user_id, error=str(e))
            # If no secretary found, get default secretary
            secretary = await self.get_secretary_assistant()

        # Create assistant instance
        assistant_instance = await self.get_assistant_by_id(
            secretary.id, user_id=str(user_id)
        )

        # Cache assistant
        self._secretary_cache[user_id] = assistant_instance

        return assistant_instance

    async def get_assistant_by_id(
        self, assistant_uuid: UUID, user_id: Optional[str] = None
    ) -> BaseAssistant:
        """Get or create assistant instance by its UUID.

        Args:
            assistant_uuid: The UUID of the assistant.
            user_id: The string ID of the user requesting the assistant (needed for tool init).

        Returns:
            Assistant instance.

        Raises:
            ValueError: If assistant not found or type is unknown.
        """
        # Check cache first
        if assistant_uuid in self._assistant_cache:
            return self._assistant_cache[assistant_uuid]

        logger.info("Getting assistant by UUID", assistant_uuid=assistant_uuid)

        try:
            assistant_data = await self.rest_client.get_assistant(str(assistant_uuid))
        except Exception as e:
            logger.error(
                "Failed to get assistant by UUID",
                assistant_uuid=assistant_uuid,
                error=str(e),
                exc_info=True,
            )
            raise ValueError(f"Assistant with UUID {assistant_uuid} not found.") from e

        # Ensure user_id is provided if needed
        if user_id is None:
            # This case should ideally be handled by the caller (e.g., get_user_secretary)
            # but add a safeguard here.
            logger.error(
                "user_id is None when calling get_assistant_by_id, tool initialization might fail",
                assistant_uuid=assistant_uuid,
            )
            # Depending on strictness, could raise: raise ValueError("user_id cannot be None")
            # For now, allow it but expect potential downstream errors from tools.

        # Prepare config dicts for BaseAssistant
        # The config fields (temperature, timeout, api_key etc.) are stored in the nested assistant_data.config dict.
        # Need to safely access this dict and its keys.
        assistant_config_dict = getattr(assistant_data, "config", None) or {}

        config = {
            "api_key": assistant_config_dict.get(
                "api_key", self.settings.OPENAI_API_KEY
            ),
            "model_name": assistant_data.model,
            "temperature": assistant_config_dict.get("temperature", 0.7),
            "system_prompt": assistant_data.instructions,
            "timeout": assistant_config_dict.get("timeout", 60),
            **assistant_config_dict,
        }
        kwargs = {"is_secretary": assistant_data.is_secretary}

        # Fetch tools using the dedicated endpoint
        try:
            tool_definitions = await self.rest_client.get_assistant_tools(
                str(assistant_uuid)
            )
        except Exception as e:
            logger.error(
                "Failed to get tools for assistant",
                assistant_uuid=assistant_uuid,
                error=str(e),
                exc_info=True,
            )
            tool_definitions = []  # Default to empty list on error

        # Create tools using the ToolFactory
        # Pass user_id and assistant_id (as string)
        created_tools = self.tool_factory.create_langchain_tools(
            tool_definitions=tool_definitions,
            user_id=user_id,  # Pass the required user_id
            assistant_id=str(assistant_data.id),
        )

        # Create assistant instance
        if assistant_data.assistant_type == "llm":
            assistant_instance = LangGraphAssistant(
                assistant_id=str(assistant_data.id),
                name=assistant_data.name,
                config=config,
                tools=created_tools,  # Pass the initialized tools
                user_id=user_id,  # Pass user_id to assistant constructor
                checkpointer=self.checkpointer,
                **kwargs,
            )
        else:
            logger.error(
                f"Attempted to create assistant with unknown type: {assistant_data.assistant_type}"
            )
            raise ValueError(f"Unknown assistant type: {assistant_data.assistant_type}")

        logger.info(
            "Assistant instance created/retrieved by UUID",
            assistant_uuid=assistant_uuid,
            name=assistant_instance.name,
        )
        self._assistant_cache[assistant_uuid] = assistant_instance
        return assistant_instance

    async def get_secretary_assistant(self) -> dict:
        """Get secretary assistant config data from REST service.

        Returns:
            Secretary assistant config data (dict-like)

        Raises:
            ValueError: If secretary assistant not found
        """
        assistants = await self.rest_client.get_assistants()
        secretary_data = next((a for a in assistants if a.is_secretary), None)
        if not secretary_data:
            logger.error("Secretary assistant configuration not found in REST service.")
            raise ValueError("Secretary assistant configuration not found")
        logger.info(
            "Found secretary assistant configuration", secretary_id=secretary_data.id
        )
        return secretary_data

    async def create_main_assistant(self) -> BaseAssistant:
        """Creates the main assistant instance (secretary). Primarily for pre-warming or direct access."""
        logger.warning(
            "create_main_assistant called. Consider using get_user_secretary for user-specific instances."
        )
        secretary_data = await self.get_secretary_assistant()
        # We need a user_id here. What should it be? Using a placeholder for now.
        # This method might need rethinking if tools require a real user context.
        logger.warning(
            "Using placeholder user_id 'main_assistant_user' for create_main_assistant"
        )
        placeholder_user_id = "main_assistant_user"
        return await self.get_assistant_by_id(
            secretary_data.id, user_id=placeholder_user_id
        )

    def clear_caches(self):
        self._secretary_cache.clear()
        self._assistant_cache.clear()
        logger.info("AssistantFactory caches cleared.")
