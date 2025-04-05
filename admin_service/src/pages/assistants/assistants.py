"""Assistants page of the admin panel"""


import pandas as pd
import streamlit as st
from rest_client import AssistantCreate, AssistantUpdate, RestServiceClient
from utils.async_utils import run_async


def show_assistants_page(rest_client: RestServiceClient):
    """Display assistants page with CRUD functionality."""
    st.title("Ассистенты")

    # Получаем список ассистентов
    assistants = run_async(rest_client.get_assistants())

    if not assistants:
        st.warning("Нет доступных ассистентов")
    else:
        # Создаем DataFrame для отображения ассистентов
        assistants_data = []
        for assistant in assistants:
            assistants_data.append(
                {
                    "ID": str(assistant.id),
                    "Имя": assistant.name,
                    "Тип": assistant.assistant_type,
                    "Модель": assistant.model,
                    "Секретарь": "Да" if assistant.is_secretary else "Нет",
                    "Активен": "Да" if assistant.is_active else "Нет",
                }
            )

        assistants_df = pd.DataFrame(assistants_data)

        # Отображаем таблицу ассистентов
        st.subheader("Список ассистентов")

        # Отображаем таблицу и кнопки в колонках
        col1, col2 = st.columns([4, 1])

        with col1:
            st.dataframe(assistants_df, hide_index=True, use_container_width=True)

        with col2:
            for assistant in assistants:
                col_edit, col_delete = st.columns(2)
                with col_edit:
                    if st.button(
                        "✏️", key=f"edit_{assistant.id}", help="Редактировать"
                    ):
                        st.session_state["editing_assistant"] = assistant
                        st.rerun()
                with col_delete:
                    if st.button("🗑️", key=f"delete_{assistant.id}", help="Удалить"):
                        st.session_state["deleting_assistant"] = assistant
                        st.rerun()

    # Секция создания нового ассистента
    with st.expander("➕ Создать нового ассистента", expanded=False):
        with st.form("create_assistant_form"):
            name = st.text_input("Имя")
            is_secretary = st.checkbox("Является секретарем")
            model = st.text_input("Модель")
            instructions = st.text_area("Инструкции")
            assistant_type = st.selectbox("Тип ассистента", ["llm", "openai_api"])
            openai_assistant_id = st.text_input("ID ассистента OpenAI (опционально)")

            submit_button = st.form_submit_button("Создать ассистента")

            if submit_button:
                if not name or not model or not instructions:
                    st.error("Пожалуйста, заполните все обязательные поля")
                else:
                    with st.spinner("Создаем ассистента..."):
                        new_assistant = AssistantCreate(
                            name=name,
                            is_secretary=is_secretary,
                            model=model,
                            instructions=instructions,
                            assistant_type=assistant_type,
                            openai_assistant_id=openai_assistant_id
                            if openai_assistant_id
                            else None,
                        )
                        created_assistant = run_async(
                            rest_client.create_assistant(new_assistant)
                        )
                        st.success(f"Ассистент {created_assistant.name} успешно создан")
                        st.rerun()

    # Секция редактирования ассистента
    if "editing_assistant" in st.session_state:
        assistant = st.session_state["editing_assistant"]
        st.subheader(f"Редактировать ассистента: {assistant.name}")

        with st.form("edit_assistant_form"):
            new_name = st.text_input("Имя", value=assistant.name)
            new_is_secretary = st.checkbox(
                "Является секретарем", value=assistant.is_secretary
            )
            new_model = st.text_input("Модель", value=assistant.model)
            new_instructions = st.text_area("Инструкции", value=assistant.instructions)
            new_assistant_type = st.selectbox(
                "Тип ассистента",
                ["llm", "openai_api"],
                index=0 if assistant.assistant_type == "llm" else 1,
            )
            new_openai_assistant_id = st.text_input(
                "ID ассистента OpenAI (опционально)",
                value=assistant.openai_assistant_id or "",
            )
            new_is_active = st.checkbox("Активен", value=assistant.is_active)

            col1, col2 = st.columns(2)
            with col1:
                submit_button = st.form_submit_button("Обновить ассистента")
            with col2:
                cancel_button = st.form_submit_button("Отмена")

            if submit_button:
                if not new_name or not new_model or not new_instructions:
                    st.error("Пожалуйста, заполните все обязательные поля")
                else:
                    with st.spinner("Обновляем ассистента..."):
                        updated_assistant = AssistantUpdate(
                            name=new_name,
                            is_secretary=new_is_secretary,
                            model=new_model,
                            instructions=new_instructions,
                            assistant_type=new_assistant_type,
                            openai_assistant_id=new_openai_assistant_id
                            if new_openai_assistant_id
                            else None,
                            is_active=new_is_active,
                        )
                        run_async(
                            rest_client.update_assistant(
                                assistant.id, updated_assistant
                            )
                        )
                        st.success(f"Ассистент {new_name} успешно обновлен")
                        del st.session_state["editing_assistant"]
                        st.rerun()

            if cancel_button:
                del st.session_state["editing_assistant"]
                st.rerun()

    # Секция удаления ассистента
    if "deleting_assistant" in st.session_state:
        assistant = st.session_state["deleting_assistant"]
        st.subheader(f"Удалить ассистента: {assistant.name}")

        st.warning(
            f"Вы уверены, что хотите удалить ассистента '{assistant.name}'? Это действие нельзя отменить."
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Подтвердить удаление"):
                with st.spinner("Удаляем ассистента..."):
                    run_async(rest_client.delete_assistant(assistant.id))
                    st.success(f"Ассистент {assistant.name} успешно удален")
                    del st.session_state["deleting_assistant"]
                    st.rerun()

        with col2:
            if st.button("Отмена"):
                del st.session_state["deleting_assistant"]
                st.rerun()
