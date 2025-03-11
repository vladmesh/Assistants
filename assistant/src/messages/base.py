from langchain_core.messages import HumanMessage as LangHumanMessage, BaseMessage
from langchain_core.messages import AIMessage as LangAIMessage
from typing import List
import datetime




class HumanMessage(LangHumanMessage):
    pass

class AIMessage(LangAIMessage):
    pass


class MessagesThread:
    """Thread for storing conversation"""

    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self.messages: List[BaseMessage] = []
        self.created_at: datetime = datetime.datetime.now(datetime.UTC)
        self.updated_at: datetime = self.created_at

    def add_message(self, message: BaseMessage):
        """Add a new message to the thread"""
        self.messages.append(message)
        self.updated_at = datetime.datetime.now(datetime.UTC)

    def get_messages(self) -> List[BaseMessage]:
        """Get all messages in the thread"""
        return self.messages
