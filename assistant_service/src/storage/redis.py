"""Redis storage implementation."""
from typing import Any, List, Optional
import json
import redis.asyncio as redis
from messages.base import BaseMessage

class RedisStorage:
    """Redis storage for chat history and tool results."""
    
    def __init__(self, redis_client: redis.Redis):
        """Initialize Redis storage.
        
        Args:
            redis_client: Redis client instance
        """
        self.redis = redis_client
    
    async def save_chat_history(self, user_id: str, messages: List[BaseMessage]) -> None:
        """Save chat history for a user.
        
        Args:
            user_id: User identifier
            messages: List of chat messages
        """
        key = f"chat_history:{user_id}"
        serialized = json.dumps([msg.dict() for msg in messages])
        await self.redis.set(key, serialized)
    
    async def get_chat_history(self, user_id: str) -> List[BaseMessage]:
        """Get chat history for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of chat messages
        """
        key = f"chat_history:{user_id}"
        data = await self.redis.get(key)
        if not data:
            return []
            
        messages_data = json.loads(data)
        return [BaseMessage.parse_obj(msg) for msg in messages_data]
    
    async def save_tool_result(self, tool_name: str, input_hash: str, result: Any) -> None:
        """Save tool execution result.
        
        Args:
            tool_name: Name of the tool
            input_hash: Hash of the input parameters
            result: Tool execution result
        """
        key = f"tool_cache:{tool_name}:{input_hash}"
        await self.redis.set(key, json.dumps(result))
    
    async def get_tool_result(self, tool_name: str, input_hash: str) -> Optional[Any]:
        """Get cached tool execution result.
        
        Args:
            tool_name: Name of the tool
            input_hash: Hash of the input parameters
            
        Returns:
            Cached result or None if not found
        """
        key = f"tool_cache:{tool_name}:{input_hash}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None 