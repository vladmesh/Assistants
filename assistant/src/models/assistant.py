from typing import List, Dict, Any
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import BaseTool
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Assistant:
    def __init__(
        self,
        tools: List[BaseTool],
        model_name: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
    ):
        self.tools = tools
        api_key = os.getenv("OPENAI_API_KEY")
        logger.info(f"Initializing ChatOpenAI with key prefix: {api_key[:10]}...")
        
        self.llm = ChatOpenAI(
            model_name=model_name,
            temperature=temperature
        )
        
        # Create the prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant that can use various tools to help users. "
                      "Always think carefully about which tool to use and explain your reasoning."),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        # Create the agent
        self.agent = create_openai_tools_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        # Create the agent executor
        self.agent_executor = AgentExecutor.from_agent_and_tools(
            agent=self.agent,
            tools=self.tools,
            verbose=True
        )
    
    async def process_message(self, message: str) -> Dict[str, Any]:
        """
        Process a user message and return the response.
        """
        try:
            logger.info(f"Processing message: {message}")
            response = await self.agent_executor.ainvoke({"input": message})
            logger.info(f"Got response: {response}")
            return {
                "status": "success",
                "response": response["output"],
                "error": None
            }
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return {
                "status": "error",
                "response": None,
                "error": str(e)
            } 