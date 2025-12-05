"""Assistants page of the admin panel"""


import pandas as pd
import streamlit as st
from rest_client import RestServiceClient
from utils.async_utils import run_async

from shared_models.api_schemas import AssistantCreate, AssistantUpdate


def show_assistants_page(rest_client: RestServiceClient):
    """Display assistants page with CRUD functionality."""
    st.title("Ассистенты")

    # Получаем список ассистентов и инструментов
    assistants = run_async(rest_client.get_assistants())
    all_tools = run_async(rest_client.get_tools())

    if not assistants:
        st.warning("Нет доступных ассистентов")
    else:
        # Создаем DataFrame для отображения ассистентов
        assistants_data = []
        for assistant in assistants:
            # Получаем инструменты ассистента
            assistant_tools = run_async(rest_client.get_assistant_tools(assistant.id))
            tools_count = len(assistant_tools)

            assistants_data.append(
                {
                    "ID": str(assistant.id),
                    "Имя": assistant.name,
                    "Тип": assistant.assistant_type,
                    "Модель": assistant.model,
                    "Секретарь": "Да" if assistant.is_secretary else "Нет",
                    "Активен": "Да" if assistant.is_active else "Нет",
                    "Инструменты": f"{tools_count} шт.",
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
                col_edit, col_delete, col_tools = st.columns(3)
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
                with col_tools:
                    if st.button(
                        "🛠️",
                        key=f"tools_{assistant.id}",
                        help="Управление инструментами",
                    ):
                        st.session_state["managing_tools"] = assistant
                        st.rerun()

    # Секция управления инструментами
    if "managing_tools" in st.session_state:
        assistant = st.session_state["managing_tools"]
        st.subheader(f"Управление инструментами: {assistant.name}")

        # Получаем текущие инструменты ассистента
        assistant_tools = run_async(rest_client.get_assistant_tools(assistant.id))

        # Отображаем текущие инструменты
        if assistant_tools:
            st.write("Текущие инструменты:")
            for tool in assistant_tools:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"- {tool.name} ({tool.tool_type})")
                with col2:
                    if st.button(
                        "🗑️", key=f"remove_tool_{tool.id}", help="Удалить инструмент"
                    ):
                        with st.spinner("Удаляем инструмент..."):
                            run_async(
                                rest_client.remove_tool_from_assistant(
                                    assistant.id, tool.id
                                )
                            )
                            st.success(f"Инструмент {tool.name} удален")
                            st.rerun()
        else:
            st.info("У ассистента пока нет инструментов")

        # Форма добавления нового инструмента
        with st.form("add_tool_form"):
            # Фильтруем инструменты, которые еще не назначены ассистенту
            available_tools = [
                t for t in all_tools if t.id not in [at.id for at in assistant_tools]
            ]

            if available_tools:
                selected_tool = st.selectbox(
                    "Выберите инструмент для добавления",
                    options=available_tools,
                    format_func=lambda x: f"{x.name} ({x.tool_type})",
                )

                submit_button = st.form_submit_button("Добавить инструмент")

                if submit_button:
                    with st.spinner("Добавляем инструмент..."):
                        run_async(
                            rest_client.add_tool_to_assistant(
                                assistant.id, selected_tool.id
                            )
                        )
                        st.success(f"Инструмент {selected_tool.name} добавлен")
                        st.rerun()
            else:
                st.info("Нет доступных инструментов для добавления")

        # Кнопка возврата
        if st.button("Назад"):
            del st.session_state["managing_tools"]
            st.rerun()

    # Секция создания нового ассистента
    with st.expander("➕ Создать нового ассистента", expanded=False):
        with st.form("create_assistant_form"):
            name = st.text_input("Имя")
            description = st.text_area("Описание")
            is_secretary = st.checkbox("Является секретарем")
            model = st.text_input("Модель")
            instructions = st.text_area("Инструкции")
            assistant_type = st.selectbox("Тип ассистента", ["llm"])
            startup_message = st.text_area("Стартовое сообщение")

            submit_button = st.form_submit_button("Создать ассистента")

            if submit_button:
                if not name or not model or not instructions:
                    st.error("Пожалуйста, заполните все обязательные поля: Имя, Модель, Инструкции")
                else:
                    with st.spinner("Создаем ассистента..."):
                        new_assistant = AssistantCreate(
                            name=name,
                            description=description,
                            is_secretary=is_secretary,
                            model=model,
                            instructions=instructions,
                            assistant_type=assistant_type,
                            startup_message=startup_message,
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
            new_description = st.text_area(
                "Описание", value=getattr(assistant, "description", None) or ""
            )
            new_is_secretary = st.checkbox(
                "Является секретарем", value=assistant.is_secretary
            )
            new_model = st.text_input("Модель", value=assistant.model)
            new_instructions = st.text_area("Инструкции", value=assistant.instructions)
            new_assistant_type = st.selectbox(
                "Тип ассистента",
                ["llm"],
                index=0,
            )
            new_is_active = st.checkbox("Активен", value=assistant.is_active)
            new_startup_message = st.text_area(
                "Стартовое сообщение", value=getattr(assistant, "startup_message", None) or ""
            )

            col1, col2 = st.columns(2)
            with col1:
                submit_button = st.form_submit_button("Обновить ассистента")
            with col2:
                cancel_button = st.form_submit_button("Отмена")

            if submit_button:
                if not new_name or not new_model or not new_instructions:
                    st.error("Пожалуйста, заполните все обязательные поля: Имя, Модель, Инструкции")
                else:
                    with st.spinner("Обновляем ассистента..."):
                        updated_assistant = AssistantUpdate(
                            name=new_name,
                            description=new_description,
                            is_secretary=new_is_secretary,
                            model=new_model,
                            instructions=new_instructions,
                            assistant_type=new_assistant_type,
                            is_active=new_is_active,
                            startup_message=new_startup_message,
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
