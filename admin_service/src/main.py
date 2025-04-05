import asyncio
import logging
from typing import List, Optional, Tuple
from uuid import UUID

import pandas as pd
import streamlit as st
import structlog
from config import settings
from rest_client import (
    Assistant,
    AssistantCreate,
    AssistantUpdate,
    RestServiceClient,
    User,
)

# Настройка логирования
logging.basicConfig(level=settings.LOG_LEVEL)
logger = structlog.get_logger()

# Инициализация клиента REST API
rest_client = RestServiceClient()


def get_event_loop():
    """Получить или создать event loop для текущей сессии Streamlit."""
    if "loop" not in st.session_state:
        st.session_state.loop = asyncio.new_event_loop()
    return st.session_state.loop


def run_async(coro):
    """Безопасный запуск асинхронных корутин в Streamlit."""
    loop = get_event_loop()
    return loop.run_until_complete(coro)


async def get_users() -> List[User]:
    """Получить список пользователей из REST API."""
    try:
        return await rest_client.get_users()
    except Exception as e:
        logger.error("Ошибка при получении пользователей", error=str(e))
        st.error(f"Ошибка при получении пользователей: {str(e)}")
        return []


async def get_assistants() -> List[Assistant]:
    """Получить список ассистентов из REST API."""
    try:
        return await rest_client.get_assistants()
    except Exception as e:
        logger.error("Ошибка при получении ассистентов", error=str(e))
        st.error(f"Ошибка при получении ассистентов: {str(e)}")
        return []


async def create_assistant(assistant: AssistantCreate) -> Assistant:
    """Создать нового ассистента."""
    try:
        return await rest_client.create_assistant(assistant)
    except Exception as e:
        logger.error("Ошибка при создании ассистента", error=str(e))
        st.error(f"Ошибка при создании ассистента: {str(e)}")
        return None


async def update_assistant(assistant_id: UUID, assistant: AssistantUpdate) -> Assistant:
    """Обновить ассистента."""
    try:
        return await rest_client.update_assistant(assistant_id, assistant)
    except Exception as e:
        logger.error("Ошибка при обновлении ассистента", error=str(e))
        st.error(f"Ошибка при обновлении ассистента: {str(e)}")
        return None


async def delete_assistant(assistant_id: UUID) -> None:
    """Удалить ассистента."""
    try:
        await rest_client.delete_assistant(assistant_id)
        st.success("Ассистент успешно удален")
    except Exception as e:
        logger.error("Ошибка при удалении ассистента", error=str(e))
        st.error(f"Ошибка при удалении ассистента: {str(e)}")


async def set_user_secretary(user_id: int, secretary_id: UUID) -> None:
    """Назначить секретаря пользователю."""
    try:
        await rest_client.set_user_secretary(user_id, secretary_id)
        st.success("Секретарь успешно назначен")
    except Exception as e:
        logger.error("Ошибка при назначении секретаря", error=str(e))
        st.error(f"Ошибка при назначении секретаря: {str(e)}")


async def get_secretary_assistants() -> List[Assistant]:
    """Получить список ассистентов-секретарей."""
    try:
        assistants = await rest_client.get_assistants()
        return [a for a in assistants if a.is_secretary and a.is_active]
    except Exception as e:
        logger.error("Ошибка при получении списка секретарей", error=str(e))
        st.error(f"Ошибка при получении списка секретарей: {str(e)}")
        return []


async def get_users_and_secretaries() -> Tuple[List[User], List[Assistant]]:
    """Получить список пользователей и секретарей."""
    try:
        users = await get_users()
        secretaries = await get_secretary_assistants()
        return users, secretaries
    except Exception as e:
        logger.error("Ошибка при получении данных", error=str(e))
        st.error(f"Ошибка при получении данных: {str(e)}")
        return [], []


def show_users_page():
    """Показать страницу пользователей."""
    st.header("Users")

    # Получаем список пользователей и секретарей
    users, secretary_assistants = run_async(get_users_and_secretaries())

    if not users:
        st.info("No users found.")
        return

    # Создаем словарь для хранения выбранных секретарей
    if "selected_secretaries" not in st.session_state:
        st.session_state.selected_secretaries = {}

    # Создаем DataFrame для отображения
    df = pd.DataFrame(
        [
            {
                "ID": user.id,
                "Telegram ID": user.telegram_id,
                "Username": user.username,
            }
            for user in users
        ]
    )

    # Отображаем таблицу пользователей
    st.dataframe(df, use_container_width=True)

    # Секция назначения секретаря
    st.subheader("Assign Secretary")

    # Выбор пользователя
    user_options = {f"{u.username or u.telegram_id} (ID: {u.id})": u.id for u in users}
    selected_user = st.selectbox(
        "Select User", options=list(user_options.keys()), format_func=lambda x: x
    )

    if selected_user:
        user_id = user_options[selected_user]

        # Выбор секретаря
        secretary_options = {
            f"{a.name} ({a.model})": a.id for a in secretary_assistants
        }
        secretary_options["None"] = None

        # Получаем текущий выбор из session_state или используем "None"
        current_secretary = st.session_state.selected_secretaries.get(user_id, "None")

        selected_secretary = st.selectbox(
            "Select Secretary",
            options=list(secretary_options.keys()),
            index=list(secretary_options.keys()).index(current_secretary)
            if current_secretary in secretary_options
            else 0,
            key=f"secretary_select_{user_id}",
        )

        # Кнопка назначения секретаря
        if st.button("Assign Secretary", key=f"assign_secretary_{user_id}"):
            secretary_id = secretary_options[selected_secretary]

            if secretary_id:
                with st.spinner("Assigning secretary..."):
                    run_async(set_user_secretary(user_id, secretary_id))
                    st.session_state.selected_secretaries[user_id] = selected_secretary
            else:
                st.warning("Please select a secretary to assign")


def show_assistants_page():
    """Показать страницу ассистентов."""
    st.header("Assistants")

    # Кнопка создания нового ассистента
    if st.button("Create New Assistant"):
        st.session_state.show_create_assistant = True

    # Форма создания нового ассистента
    if st.session_state.get("show_create_assistant", False):
        with st.form("create_assistant_form"):
            st.subheader("Create New Assistant")
            name = st.text_input("Name")
            is_secretary = st.checkbox("Is Secretary")
            model = st.text_input("Model", value="gpt-4-turbo-preview")
            instructions = st.text_area("Instructions")
            assistant_type = st.selectbox(
                "Assistant Type", options=["llm", "openai_api"], index=0
            )
            openai_assistant_id = st.text_input("OpenAI Assistant ID (optional)")

            if st.form_submit_button("Create"):
                assistant = AssistantCreate(
                    name=name,
                    is_secretary=is_secretary,
                    model=model,
                    instructions=instructions,
                    assistant_type=assistant_type,
                    openai_assistant_id=openai_assistant_id or None,
                )
                result = run_async(create_assistant(assistant))
                if result:
                    st.success("Assistant created successfully!")
                    st.session_state.show_create_assistant = False
                    st.rerun()

    # Форма редактирования ассистента
    if st.session_state.get("editing_assistant"):
        assistant = st.session_state.editing_assistant
        with st.form(f"edit_assistant_form_{assistant.id}"):
            st.subheader(f"Edit Assistant: {assistant.name}")

            name = st.text_input("Name", value=assistant.name)
            is_secretary = st.checkbox("Is Secretary", value=assistant.is_secretary)
            model = st.text_input("Model", value=assistant.model)
            instructions = st.text_area("Instructions", value=assistant.instructions)
            assistant_type = st.selectbox(
                "Assistant Type",
                options=["llm", "openai_api"],
                index=0 if assistant.assistant_type == "llm" else 1,
            )
            openai_assistant_id = st.text_input(
                "OpenAI Assistant ID (optional)",
                value=assistant.openai_assistant_id or "",
            )
            is_active = st.checkbox("Is Active", value=assistant.is_active)

            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Save Changes"):
                    assistant_update = AssistantUpdate(
                        name=name,
                        is_secretary=is_secretary,
                        model=model,
                        instructions=instructions,
                        assistant_type=assistant_type,
                        openai_assistant_id=openai_assistant_id or None,
                        is_active=is_active,
                    )
                    result = run_async(update_assistant(assistant.id, assistant_update))
                    if result:
                        st.success("Assistant updated successfully!")
                        st.session_state.editing_assistant = None
                        st.rerun()

            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.editing_assistant = None
                    st.rerun()

    # Список ассистентов
    assistants = run_async(get_assistants())
    if assistants:
        for assistant in assistants:
            with st.expander(f"{assistant.name} ({assistant.assistant_type})"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Details:**")
                    st.write(f"ID: {assistant.id}")
                    st.write(f"Model: {assistant.model}")
                    st.write(f"Is Secretary: {assistant.is_secretary}")
                    st.write(f"Is Active: {assistant.is_active}")

                with col2:
                    st.write("**Instructions:**")
                    st.text(assistant.instructions)

                # Кнопки действий
                if st.button("Edit", key=f"edit_{assistant.id}"):
                    st.session_state.editing_assistant = assistant

                if st.button("Delete", key=f"delete_{assistant.id}"):
                    if st.button(
                        "Confirm Delete", key=f"confirm_delete_{assistant.id}"
                    ):
                        run_async(delete_assistant(assistant.id))
                        st.rerun()
    else:
        st.info("No assistants found.")


def main():
    """Основная функция приложения."""
    st.set_page_config(
        page_title="Admin Panel",
        page_icon="👨‍💼",
        layout="wide",
    )

    st.title("Admin Panel")

    # Навигация
    page = st.sidebar.radio("Navigation", ["Users", "Assistants"])

    if page == "Users":
        show_users_page()
    elif page == "Assistants":
        show_assistants_page()


if __name__ == "__main__":
    main()
