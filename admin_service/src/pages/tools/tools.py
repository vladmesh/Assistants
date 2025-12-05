"""Tools page of the admin panel"""

from uuid import UUID

import pandas as pd
import streamlit as st
from shared_models.api_schemas import ToolCreate, ToolUpdate
from shared_models.enums import ToolType

from rest_client import RestServiceClient
from utils.async_utils import run_async


def show_tools_page(rest_client: RestServiceClient):
    """Display tools page with management functionality."""
    st.title("Инструменты")

    # Получаем список инструментов и ассистентов
    tools = run_async(rest_client.get_tools())
    run_async(rest_client.get_assistants())

    if not tools:
        st.warning("Нет доступных инструментов")
    else:
        # Создаем DataFrame для отображения инструментов
        tools_data = []
        for tool in tools:
            tools_data.append(
                {
                    "ID": str(tool.id),
                    "Имя": tool.name,
                    "Тип": tool.tool_type,
                    "Описание": tool.description,
                    "Активен": "Да" if tool.is_active else "Нет",
                }
            )

        tools_df = pd.DataFrame(tools_data)

        # Отображаем таблицу инструментов
        st.subheader("Список инструментов")
        st.dataframe(tools_df, hide_index=True, use_container_width=True)

        # Секция редактирования инструмента
        st.subheader("Редактирование инструмента")

        # Создаем список инструментов для выпадающего списка
        tool_options = {f"{tool.name} ({tool.tool_type})": tool for tool in tools}
        selected_tool_name = st.selectbox(
            "Выберите инструмент для редактирования",
            options=list(tool_options.keys()),
            index=None,
            placeholder="Выберите инструмент...",
        )

        if selected_tool_name:
            tool = tool_options[selected_tool_name]

            with st.expander("Форма редактирования", expanded=True):
                with st.form("edit_tool_form"):
                    st.write(f"**Редактирование инструмента:** {tool.name}")
                    new_description = st.text_area("Описание", value=tool.description)
                    new_is_active = st.checkbox("Активен", value=tool.is_active)

                    col1, col2, col3 = st.columns([1, 1, 1])
                    with col1:
                        submit_button = st.form_submit_button("💾 Сохранить")
                    with col2:
                        cancel_button = st.form_submit_button("❌ Отмена")
                    with col3:
                        delete_button = st.form_submit_button("🗑️ Удалить")

                    if submit_button:
                        with st.spinner("Обновляем инструмент..."):
                            updated_tool = ToolUpdate(
                                description=new_description,
                                is_active=new_is_active,
                            )
                            run_async(rest_client.update_tool(tool.id, updated_tool))
                            st.success(f"Инструмент {tool.name} успешно обновлен")
                            st.rerun()

                    if cancel_button:
                        st.rerun()

                    if delete_button:
                        if st.checkbox("Подтвердите удаление", key="confirm_delete"):
                            with st.spinner("Удаляем инструмент..."):
                                run_async(rest_client.delete_tool(tool.id))
                                st.success(f"Инструмент {tool.name} успешно удален")
                                st.rerun()

    # Секция создания нового инструмента
    st.subheader("Create New Tool")
    with st.form("create_tool_form"):
        name = st.text_input("Name")
        tool_type = st.selectbox("Type", options=[t.value for t in ToolType])
        description = st.text_area("Description")
        assistant_id_str = st.text_input(
            "Assistant ID (for sub_assistant type)",
            help="Only required if tool_type is 'sub_assistant'",
        )
        submitted = st.form_submit_button("Create Tool")
        if submitted:
            if not name or not description:
                st.error("Name and Description are required fields.")
            else:
                assistant_id = None
                if tool_type == ToolType.SUB_ASSISTANT.value and assistant_id_str:
                    try:
                        assistant_id = UUID(assistant_id_str)
                    except ValueError:
                        st.error("Invalid Assistant ID format.")
                        assistant_id = None  # Reset to None if invalid

                if tool_type != ToolType.SUB_ASSISTANT.value or assistant_id:
                    try:
                        # Create ToolCreate object
                        tool_data = ToolCreate(
                            name=name,
                            tool_type=ToolType(tool_type),
                            description=description,
                            assistant_id=assistant_id,
                            # Params are not handled by this simple form yet
                            parameters={},
                        )
                        # Call create_tool with the object
                        run_async(rest_client.create_tool(tool=tool_data))
                        st.success("Tool created successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to create tool: {e}")
                elif tool_type == ToolType.SUB_ASSISTANT.value and not assistant_id:
                    st.error("Assistant ID is required for sub_assistant type.")
