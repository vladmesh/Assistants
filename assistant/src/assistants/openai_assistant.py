"""OpenAI Assistants API implementation"""
import logging
from typing import List, Optional, Any, Dict
from openai import OpenAI
import json
import asyncio
import time

from assistants.base import BaseAssistant
from tools.base import BaseTool
from config.logger import get_logger

# Configure logging
logger = get_logger(__name__)

# Constants
MAX_WAIT_TIME = 30  # Maximum time to wait for run completion in seconds
STATUS_CHECK_INTERVAL = 3  # Time between status checks in seconds

class OpenAIAssistant(BaseAssistant):
    """Assistant implementation using OpenAI Assistants API"""
    
    def __init__(
        self,
        assistant_id: Optional[str] = None,
        instructions: Optional[str] = None,
        name: Optional[str] = None,
        model: str = "gpt-4-turbo-preview",
        tools: Optional[List[Dict]] = None,
        tool_instances: Optional[List[BaseTool]] = None
    ):
        """Initialize OpenAI Assistant
        
        Args:
            assistant_id: ID of existing assistant to use
            instructions: System instructions for new assistant
            name: Name for new assistant
            model: Model to use for new assistant
            tools: List of tool schemas for new assistant
            tool_instances: List of actual tool instances for execution
        """
        # Initialize base class
        super().__init__(
            name=name or "openai_assistant",
            instructions=instructions or "",
            tools=tool_instances
        )
        
        logger.info("initializing_openai_assistant")
        self.client = OpenAI()
        self.thread_id: Optional[str] = None
        self.tool_instances = {tool.name: tool for tool in (tool_instances or [])}
        
        # Create or retrieve assistant
        if assistant_id:
            self.assistant = self.client.beta.assistants.retrieve(assistant_id)
            if tools is not None:
                # Update assistant with new tools if provided
                self.assistant = self.client.beta.assistants.update(
                    assistant_id=assistant_id,
                    tools=tools,
                    instructions=instructions
                )
        else:
            self.assistant = self.client.beta.assistants.create(
                name=name,
                instructions=instructions,
                model=model,
                tools=tools
            )

    def update_assistant(
        self,
        tools: Optional[List[dict]] = None,
        instructions: Optional[str] = None,
        model: Optional[str] = None,
        name: Optional[str] = None
    ) -> None:
        """Update existing assistant with new configuration
        
        Args:
            tools: New tools configuration
            instructions: New system instructions
            model: New model to use
            name: New assistant name
        """
        try:
            update_params = {}
            if tools is not None:
                update_params["tools"] = tools
            if instructions is not None:
                update_params["instructions"] = instructions
            if model is not None:
                update_params["model"] = model
            if name is not None:
                update_params["name"] = name
                
            if update_params:
                logger.info("updating_assistant", assistant_id=self.assistant.id, **update_params)
                self.assistant = self.client.beta.assistants.update(
                    assistant_id=self.assistant.id,
                    **update_params
                )
                logger.info("assistant_updated", assistant_id=self.assistant.id)
        except Exception as e:
            logger.error("assistant_update_failed", 
                        assistant_id=self.assistant.id,
                        error=str(e),
                        exc_info=True)
            raise

    async def process_message(self, message: Any, user_id: Optional[str] = None) -> str:
        """Process a message using the OpenAI Assistant
        
        Args:
            message: Message to process (will be converted to string)
            user_id: Optional user identifier for thread management
            
        Returns:
            Assistant's response as string
        """
        try:
            # Set tool context
            self._set_tool_context(user_id)
            
            # Create thread if needed
            if not self.thread_id:
                logger.info("creating_thread")
                thread = self.client.beta.threads.create()
                self.thread_id = thread.id
                logger.info("thread_created", thread_id=self.thread_id)
            
            # Check for active runs and wait for them to complete
            runs = self.client.beta.threads.runs.list(thread_id=self.thread_id)
            for run in runs.data:
                if run.status in ["queued", "in_progress"]:
                    logger.info("waiting_for_active_run", run_id=run.id, status=run.status)
                    start_time = time.time()
                    while run.status in ["queued", "in_progress"]:
                        if time.time() - start_time > MAX_WAIT_TIME:
                            logger.error("run_timeout", run_id=run.id, status=run.status)
                            raise Exception(f"Run timed out after {MAX_WAIT_TIME} seconds")
                        await asyncio.sleep(STATUS_CHECK_INTERVAL)
                        run = self.client.beta.threads.runs.retrieve(
                            thread_id=self.thread_id,
                            run_id=run.id
                        )
                    logger.info("active_run_completed", run_id=run.id, final_status=run.status)
            
            # Add message to thread
            logger.info("adding_message", thread_id=self.thread_id)
            self.client.beta.threads.messages.create(
                thread_id=self.thread_id,
                role="user",
                content=str(message)
            )
            
            # Run assistant
            logger.info("starting_run", thread_id=self.thread_id)
            run = self.client.beta.threads.runs.create(
                thread_id=self.thread_id,
                assistant_id=self.assistant.id
            )
            
            # Wait for completion and handle tool calls
            start_time = time.time()
            while True:
                if time.time() - start_time > MAX_WAIT_TIME:
                    logger.error("run_timeout", run_id=run.id)
                    raise Exception(f"Run timed out after {MAX_WAIT_TIME} seconds")
                
                await asyncio.sleep(STATUS_CHECK_INTERVAL)
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=self.thread_id,
                    run_id=run.id
                )
                logger.debug("run_status", status=run.status)
                
                if run.status == "requires_action":
                    # Handle tool calls
                    tool_calls = run.required_action.submit_tool_outputs.tool_calls
                    tool_outputs = []
                    
                    logger.info("processing_tool_calls", count=len(tool_calls))
                    for tool_call in tool_calls:
                        try:
                            # Parse tool call arguments
                            function_name = tool_call.function.name
                            arguments = json.loads(tool_call.function.arguments)
                            
                            logger.info("executing_tool", 
                                      tool_id=tool_call.id,
                                      function=function_name,
                                      arguments=arguments)
                            
                            # Execute tool call
                            result = await self._execute_tool_call(function_name, arguments)
                            
                            tool_outputs.append({
                                "tool_call_id": tool_call.id,
                                "output": str(result)
                            })
                            
                            logger.info("tool_execution_completed", 
                                      tool_id=tool_call.id,
                                      result=result)
                            
                        except Exception as e:
                            logger.error("tool_execution_failed",
                                       tool_id=tool_call.id,
                                       error=str(e),
                                       exc_info=True)
                            # Return error message as tool output
                            tool_outputs.append({
                                "tool_call_id": tool_call.id,
                                "output": f"Error executing tool: {str(e)}"
                            })
                    
                    # Submit tool outputs back to the assistant
                    run = self.client.beta.threads.runs.submit_tool_outputs(
                        thread_id=self.thread_id,
                        run_id=run.id,
                        tool_outputs=tool_outputs
                    )
                    # Reset timeout after submitting tool outputs
                    start_time = time.time()
                    continue
                
                if run.status == "completed":
                    logger.info("run_completed")
                    break
                    
                if run.status in ["failed", "cancelled", "expired"]:
                    logger.error("run_failed", status=run.status)
                    raise Exception(f"Run failed with status: {run.status}")
            
            # Get messages
            messages = self.client.beta.threads.messages.list(
                thread_id=self.thread_id
            )
            
            # Return latest assistant message
            for msg in messages.data:
                if msg.role == "assistant":
                    response = msg.content[0].text.value
                    logger.info("response_received")
                    return response
            
            logger.warning("no_response_found")
            return "Извините, я не смог обработать ваше сообщение"
            
        except Exception as e:
            logger.error("message_processing_failed", 
                        thread_id=self.thread_id,
                        error=str(e),
                        exc_info=True)
            raise

    async def _execute_tool_call(self, function_name: str, arguments: dict) -> str:
        """Execute a tool call from the assistant
        
        Args:
            function_name: Name of the function to execute
            arguments: Arguments for the function
            
        Returns:
            Result of the tool execution as string
            
        Raises:
            Exception: If tool execution fails
        """
        # Get tool instance
        tool = self.tool_instances.get(function_name)
        if not tool:
            raise Exception(f"Unknown tool: {function_name}")
            
        try:
            # Execute tool with arguments
            result = await tool._arun(**arguments)
            return str(result)
        except Exception as e:
            raise Exception(f"Error executing {function_name}: {str(e)}")