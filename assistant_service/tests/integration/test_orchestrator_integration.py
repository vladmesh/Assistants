# import asyncio
# import json
# import time
# import unittest.mock
# from unittest.mock import patch

# import pytest
# from assistants.factory import AssistantFactory
# from config.settings import Settings
# from httpx import patch  # Import unittest mock for ANY

# # Corrected import path
# from orchestrator import AssistantOrchestrator

# from shared_models import QueueMessage, QueueMessageSource, QueueMessageType

# from .conftest import MockChatLLMIntegration, MockRestServiceIntegration

# # Mark all tests in this file as asyncio
# pytestmark = pytest.mark.asyncio


# @pytest.fixture
# def test_user_id() -> str:
#     return "123"


# @pytest.fixture
# def assistant_factory(mock_rest_client) -> AssistantFactory:
#     """Реальная фабрика с моком REST клиента."""
#     # Передаем мок REST клиента в реальную фабрику
#     return AssistantFactory(settings=Settings(), rest_client=mock_rest_client)


# @pytest.fixture
# def orchestrator(assistant_factory) -> AssistantOrchestrator:
#     """Реальный оркестратор с реальной фабрикой."""
#     # Важно: не используем mock_settings напрямую, если они мокают input/output queue
#     # Нужны реальные имена очередей для теста
#     settings = Settings()  # Берем реальные настройки (предполагая .env.test)
#     # Можно переопределить очереди, если нужно изолировать
#     settings.redis_queue_to_secretary = "test:input:orchestrator_integration"
#     settings.redis_queue_to_telegram = "test:output:orchestrator_integration"

#     orc = AssistantOrchestrator(settings=settings)
#     # Заменяем фабрику на нашу, с моком REST
#     orc.factory = assistant_factory
#     return orc


# @pytest.fixture
# def human_queue_message(test_user_id) -> QueueMessage:
#     """Готовое сообщение для очереди."""
#     return QueueMessage(
#         user_id=test_user_id,
#         source=QueueMessageSource.TELEGRAM,
#         type=QueueMessageType.HUMAN,
#         content={"message": "Hello integration test!"},
#     )


# # Патчим ВЕЗДЕ, где ChatOpenAI может импортироваться и использоваться
# @patch(
#     "assistants.langgraph.langgraph_assistant.ChatOpenAI", new=MockChatLLMIntegration
# )
# @patch("assistants.factory.RestServiceClient", new=MockRestServiceIntegration)
# async def test_listen_for_human_message(test_redis, human_queue_message):
#     """Integration test: Check listening and processing a human message via real Redis."""
#     # Arrange
#     # Use the correct redis_url and queue names from the mock_settings fixture
#     settings = Settings()
#     settings.INPUT_QUEUE = "test:input:orchestrator_integration"
#     settings.OUTPUT_QUEUE = "test:output:orchestrator_integration"
#     orchestrator = AssistantOrchestrator(settings)
#     # Ensure the orchestrator's redis client connects to the test_redis url
#     # This should happen automatically if redis_url in mock_settings is correct
#     # and test_redis fixture uses the same url.

#     # Act: Push message to the REAL Redis queue
#     await test_redis.rpush(settings.INPUT_QUEUE, human_queue_message.model_dump_json())

#     # Start listening - run listen_for_messages in a background task
#     # as it blocks. Process only one message.
#     listen_task = asyncio.create_task(orchestrator.listen_for_messages(max_messages=1))

#     # Wait for the task to complete (with a timeout)
#     try:
#         # Increased timeout slightly for integration test with real Redis
#         await asyncio.wait_for(listen_task, timeout=7.0)
#     except asyncio.TimeoutError:
#         pytest.fail("Orchestrator did not process message within timeout")
#     finally:
#         # Ensure orchestrator redis connection is closed if initialization happened
#         if orchestrator.redis:
#             await orchestrator.redis.aclose()

#     # # Assert: Check that the response was pushed to the output queue in REAL Redis
#     # output_messages = await test_redis.lrange(settings.OUTPUT_QUEUE, 0, -1)
#     # assert len(output_messages) == 1
#     # response_data = json.loads(output_messages[0])
#     # assert response_data["type"] == QueueMessageType.SECRETARY.value
#     # assert response_data["user_id"] == 123
#     # assert response_data["response"] == "Mocked secretary response"


# # async def test_listen_for_reminder_event(
# #     mock_settings, test_redis, mock_factory, mock_secretary, reminder_trigger_event
# # ):
# #     """Integration test: Check listening and processing a reminder event via real Redis."""
# #     # Arrange
# #     mock_settings.input_queue = "test:input:orchestrator_reminder"
# #     mock_settings.output_queue = "test:output:orchestrator_reminder"
# #     orchestrator = AssistantOrchestrator(mock_settings)

# #     # Act: Push reminder event to the REAL Redis queue
# #     await test_redis.rpush(
# #         mock_settings.input_queue, json.dumps(reminder_trigger_event)
# #     )

# #     # Start listening
# #     listen_task = asyncio.create_task(orchestrator.listen_for_messages(max_messages=1))
# #     try:
# #         await asyncio.wait_for(listen_task, timeout=7.0)
# #     except asyncio.TimeoutError:
# #         pytest.fail("Orchestrator did not process reminder event within timeout")
# #     finally:
# #         if orchestrator.redis:
# #             await orchestrator.redis.aclose()

# #     # Assert: Check secretary interaction
# #     mock_factory.get_user_secretary.assert_awaited_once_with("user_reminder_123")
# #     mock_secretary.process_message.assert_awaited_once_with(
# #         message=unittest.mock.ANY,  # Check ToolMessage contents if needed
# #         user_id="user_reminder_123",
# #         triggered_event=reminder_trigger_event,
# #     )

# #     # Assert: Check response in REAL Redis output queue
# #     output_messages = await test_redis.lrange(mock_settings.output_queue, 0, -1)
# #     assert len(output_messages) == 1
# #     response_data = json.loads(output_messages[0])
# #     assert response_data["type"] == QueueMessageType.SECRETARY.value
# #     assert response_data["user_id"] == "user_reminder_123"
# #     assert response_data["response"] == "Mocked secretary response"
