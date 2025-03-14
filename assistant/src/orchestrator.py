import json
import redis.asyncio as redis
from config.logger import get_logger
from config.settings import Settings
from tools.time_tool import TimeToolWrapper
from tools.sub_assistant_tool import SubAssistantTool
from tools.reminder_tool import ReminderTool
from tools.calendar_tool import CalendarCreateTool, CalendarListTool
from assistants.factory import AssistantFactory

logger = get_logger(__name__)

class AssistantOrchestrator:
    def __init__(self, settings: Settings):
        """Initialize the assistant service."""
        # Initialize Redis connection
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        
        self.settings = settings
        
        # Initialize tools
        self.tools = []
        
        # Add time tool
        time_tool = TimeToolWrapper()
        self.tools.append(time_tool)
        
        # Initialize and add sub-assistant
        sub_assistant = AssistantFactory.create_sub_assistant(settings)
        sub_assistant_tool = SubAssistantTool(
            sub_assistant=sub_assistant,
            name="writer",
            description="""Ассистент писатель. Используй его, когда нужно написать художественый текст.
            
            Примеры использования:
            - Написать красивое поздравление
            - Сочинить стихотворение
            - Написать креативное описание
            - Придумать интересную историю
            
            Параметры:
            - message: Текст запроса для писателя"""
        )
        self.tools.append(sub_assistant_tool)

        # Add reminder tool
        reminder_tool = ReminderTool()
        self.tools.append(reminder_tool)

        # Add calendar tools
        calendar_create_tool = CalendarCreateTool(settings, user_id=None)
        calendar_list_tool = CalendarListTool(settings, user_id=None)
        self.tools.extend([calendar_create_tool, calendar_list_tool])
        
        # Initialize main assistant
        self.assistant = AssistantFactory.create_main_assistant(settings, self.tools)
        
        logger.info("Assistant service initialized",
                   tool_count=len(self.tools))
    
    async def process_message(self, message: dict) -> dict:
        """Process an incoming message."""
        try:
            user_data = message.get("user_data", {})
            user_id = str(user_data.get("id", ""))  # Use ID from user_data
            chat_id = str(message.get("chat_id", ""))
            text = message["message"]
            
            logger.info("Processing message",
                       user_id=user_id,
                       chat_id=chat_id,
                       message_length=len(text),
                       user_data=user_data)  # Log user data
            
            # Update user_id for calendar tools
            for tool in self.tools:
                if isinstance(tool, (CalendarCreateTool, CalendarListTool)):
                    tool.user_id = user_id
            
            response = await self.assistant.process_message(text, user_id)
            
            return {
                "user_id": user_id,
                "chat_id": chat_id,
                "status": "ok",
                "response": response
            }
            
        except Exception as e:
            logger.error("Message processing failed",
                        error=str(e),
                        exc_info=True)
            return {
                "user_id": message.get("user_id", ""),
                "chat_id": message.get("chat_id", ""),
                "status": "error",
                "error": str(e)
            }
    
    async def listen_for_messages(self):
        """Listen for messages from Redis queue."""
        while True:
            try:
                # Get message from input queue
                message = await self.redis.brpop(self.settings.INPUT_QUEUE, timeout=0)
                message_data = json.loads(message[1])
                
                # Process message
                result = await self.process_message(message_data)
                
                # Send result to output queue
                await self.redis.rpush(self.settings.OUTPUT_QUEUE, json.dumps(result))
                
            except Exception as e:
                logger.error("Message processing failed",
                           error=str(e),
                           exc_info=True) 