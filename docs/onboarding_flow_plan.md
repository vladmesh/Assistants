# User Onboarding Flow - Technical Plan

This document outlines the technical steps required to implement the new user onboarding flow.

## Phase 1: REST Service Changes

1.  **Modify `rest_service/src/models/assistant.py`**:
    *   Add a new field `description: Optional[str]` to the `Assistant` model. Make it optional for now.
    *   Example: `description: Optional[str] = Field(default=None)`
2.  **Modify `rest_service/src/models/user.py`**:
    *   Add a new field `timezone: Optional[str]` to the `TelegramUser` model. Make it optional initially, but it's crucial for reminders.
    *   Add a new field `preferred_name: Optional[str]` to the `TelegramUser` model. Optional.
    *   Example: `timezone: Optional[str] = Field(default=None, index=True)`
    *   Example: `preferred_name: Optional[str] = Field(default=None)`
3.  **Generate Database Migration**:
    *   Run `./manage.py migrate "Add description to Assistant and timezone/preferred_name to User"` in the terminal.
    *   Inspect the generated migration file in `rest_service/alembic/versions/`.
4.  **Apply Database Migration**:
    *   Run `./manage.py upgrade` to apply the changes to the database schema. (Ensure the DB container is running).
5.  **Modify `rest_service/src/routers/users.py`**:
    *   Add a new Pydantic schema for updating user data, e.g., `UserUpdate`.
        ```python
        class UserUpdate(BaseModel):
            timezone: Optional[str] = None
            preferred_name: Optional[str] = None
        ```
    *   Add a new endpoint `PATCH /api/users/{user_id}`.
        *   It should accept `UserUpdate` model in the request body.
        *   Retrieve the `TelegramUser` by `user_id`.
        *   Update the user's fields (`timezone`, `preferred_name`) if provided in the payload.
        *   Commit the changes and return the updated user object.
        *   Handle `404 Not Found` if the user doesn't exist.
    *   Ensure the endpoint uses `Depends(get_session)`.
6.  **Add Tests**:
    *   Add tests in `rest_service/tests/` to verify:
        *   The new fields are present in `Assistant` and `TelegramUser` responses.
        *   The new `PATCH /api/users/{user_id}` endpoint works correctly.

## Phase 2: Telegram Bot Service Changes

1.  **Modify `telegram_bot_service/src/main.py` (`process_message` function)**:
    *   **Before** calling `rest.get_or_create_user`:
        *   Check if `message_text == "/start"`. If yes, proceed as currently (call `get_or_create_user` and then `handle_start`).
        *   If `message_text != "/start"`:
            *   Call a **new** `rest.get_user_by_telegram_id(telegram_id)` method (needs to be added to `RestClient`). This maps to `GET /users/?telegram_id={telegram_id}` in `rest_service`.
            *   If the user exists (`get_user_by_telegram_id` returns user data), proceed with the current logic: call `get_or_create_user` (it will just retrieve the existing user) and send the message to the `input_queue`.
            *   If the user **does not exist** (`get_user_by_telegram_id` raises 404 or returns None), send a message to the user like: "Привет! Пожалуйста, используй команду /start, чтобы начать." and **do not** proceed further (don't call `get_or_create_user` or send to queue).
2.  **Add `get_user_by_telegram_id` to `telegram_bot_service/src/client/rest.py` (`RestClient` class)**:
    *   Implement the method to make a `GET` request to `/api/users/?telegram_id={telegram_id}`.
    *   Handle potential 404 errors gracefully (e.g., return `None`).
3.  **Rewrite `telegram_bot_service/src/handlers/start.py` (`handle_start` function)**:
    *   Remove the old logic sending basic greetings.
    *   Call `rest.list_secretaries()` (needs to be added to `RestClient`) to get a list of available secretaries (maps to `GET /api/secretaries/` in `rest_service`).
    *   If no secretaries are found, send an error message to the user and log the error.
    *   Format the list of secretaries for display: use `name` and the new `description` field.
    *   Use `telegram.send_message_with_inline_keyboard` (needs to be added/used in `TelegramClient`) to display the secretaries as buttons.
        *   Each button's text could be the secretary's name.
        *   Each button's callback data should uniquely identify the secretary (e.g., `select_secretary_{secretary_id}`).
    *   Send a message like "Пожалуйста, выбери своего секретаря:".
4.  **Add `list_secretaries` to `telegram_bot_service/src/client/rest.py` (`RestClient` class)**:
    *   Implement the method to make a `GET` request to `/api/secretaries/`.
5.  **Add `send_message_with_inline_keyboard` to `telegram_bot_service/src/client/telegram.py` (`TelegramClient` class)**:
    *   Implement the method to send messages with inline keyboards using the Telegram Bot API.
6.  **Handle Callback Query in `telegram_bot_service/src/main.py` (`handle_telegram_update` or new function)**:
    *   Add logic to detect `callback_query` updates.
    *   Parse the `callback_data`. If it starts with `select_secretary_`:
        *   Extract the `secretary_id`.
        *   Get `user_id` (from the callback query's `from_user`).
        *   Call `rest.set_user_secretary(user_id, secretary_id)` (needs to be added to `RestClient`, maps to `POST /api/users/{user_id}/secretary/{secretary_id}`).
        *   Answer the callback query (`telegram.answer_callback_query`).
        *   Send a confirmation message to the user (e.g., "Отлично! {secretary_name} теперь твой секретарь.").
        *   **(Optional/Advanced):** Send a special trigger message/event to `REDIS_QUEUE_TO_SECRETARY` for the `assistant_service` to start the onboarding questions. Format TBD.
7.  **Add `set_user_secretary` to `telegram_bot_service/src/client/rest.py` (`RestClient` class)**:
    *   Implement the method to make a `POST` request to `/api/users/{user_id}/secretary/{secretary_id}`.
8.  **Add Tests**:
    *   Add/update tests in `telegram_bot_service/tests/` for:
        *   New user message handling (prompting /start).
        *   `/start` command flow (listing secretaries, keyboard).
        *   Callback query handling (setting secretary).
        *   New `RestClient` methods.

## Phase 3: Assistant Service Changes

1.  **Define Onboarding Logic/Trigger**:
    *   **Option A (Trigger Message):** If implementing the trigger message from Phase 2:
        *   Modify `assistant_service/src/orchestrator.py` (`listen_for_messages`) to detect this new message type/event.
        *   When detected, call a new method on the `LangGraphAssistant` instance, e.g., `start_onboarding(user_id)`.
    *   **Option B (State Check):** Modify `assistant_service/src/assistants/langgraph_assistant.py` (`process_message` or graph logic):
        *   On receiving the *first* `HumanMessage` for a given `user_id` *after* a secretary assignment, check if onboarding data (timezone, preferred_name) is missing (requires fetching user data via REST).
        *   If data is missing, redirect the conversation flow within the LangGraph to the onboarding steps.
    *   *(Decision: Let's start with Option B for simplicity, checking user data on first interaction)*.
2.  **Implement Onboarding Questions in `LangGraphAssistant`**:
    *   Modify the LangGraph definition in `langgraph_assistant.py`.
    *   Add nodes/logic to:
        *   Check if `user.timezone` or `user.preferred_name` is null (fetch user data using `RestServiceClient`).
        *   If null, ask the user for their timezone (e.g., "Пожалуйста, укажи свой часовой пояс (например, Europe/Moscow). Это важно для напоминаний.").
        *   Wait for the user's response.
        *   Ask for their preferred name (e.g., "Как мне к тебе обращаться?").
        *   Wait for the user's response.
        *   Use a new tool (`update_user_profile`) to save the collected data.
3.  **Create `UpdateUserProfileTool`**:
    *   Create a new file `assistant_service/src/tools/user_profile_tool.py`.
    *   Define a `UserProfileSchema` (Pydantic model) for input: `timezone: Optional[str]`, `preferred_name: Optional[str]`.
    *   Create `UpdateUserProfileTool` inheriting from `BaseTool`.
    *   Implement `_execute` method:
        *   It receives `timezone` and `preferred_name`.
        *   It needs `user_id` from context (injected by `ToolFactory`).
        *   Calls the `PATCH /api/users/{user_id}` endpoint in `rest_service` using `RestServiceClient` with the provided data.
        *   Returns a success/failure message.
4.  **Register the New Tool**:
    *   Add `USER_PROFILE = "user_profile"` to `ToolType` enum in `rest_service/src/models/assistant.py` (requires another migration).
    *   Update `assistant_service/src/tools/factory.py` (`ToolFactory`):
        *   Import the new tool class.
        *   Add a case in `create_langchain_tools` or similar logic to instantiate `UpdateUserProfileTool` when `tool_data.tool_type == ToolType.USER_PROFILE`.
        *   Ensure `user_id` is correctly passed to the tool constructor.
    *   Add the tool definition to the database via `rest_service` (or fixtures) so secretaries can be configured to use it. Assign it to the default secretary initially.
5.  **Update `RestServiceClient`**:
    *   Add methods in `assistant_service/src/services/rest_service.py` for:
        *   `get_user(user_id)`: Calls `GET /api/users/{user_id}`.
        *   `update_user(user_id, data)`: Calls `PATCH /api/users/{user_id}`.
6.  **Add Tests**:
    *   Add tests in `assistant_service/tests/` for:
        *   The new `UpdateUserProfileTool`.
        *   The onboarding logic within the assistant (might require mocking REST calls).
        *   New `RestServiceClient` methods.

## Phase 4: Final Testing and Refinement

1.  **End-to-End Testing**:
    *   Manually test the entire flow with a new Telegram user.
    *   Verify database entries are created/updated correctly.
    *   Check logs for errors in all services.
2.  **Code Review and Cleanup**.
3.  **Documentation Update**: Update relevant `llm_context_*.md` files.
