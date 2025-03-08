from typing import Any, Dict, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

class BaseAssistantTool(BaseTool):
    name: str
    description: str
    args_schema: Optional[type[BaseModel]] = None
    
    @property
    def openai_schema(self) -> Dict[str, Any]:
        """Return the schema in OpenAI format."""
        schema = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.schema() if self.args_schema else {"type": "object", "properties": {}}
            }
        }
        return schema
    
    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Use the tool synchronously."""
        raise NotImplementedError("Base tool does not implement synchronous execution")
    
    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        """Use the tool asynchronously."""
        raise NotImplementedError("Base tool does not implement asynchronous execution")