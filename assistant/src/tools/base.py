from typing import Any, Dict, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

class BaseAssistantTool(BaseTool):
    name: str
    description: str
    args_schema: Optional[type[BaseModel]] = None
    
    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Use the tool synchronously."""
        raise NotImplementedError("Base tool does not implement synchronous execution")
    
    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        """Use the tool asynchronously."""
        raise NotImplementedError("Base tool does not implement asynchronous execution") 