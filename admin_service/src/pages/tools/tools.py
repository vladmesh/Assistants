"""Tools page of the admin panel"""

import pandas as pd
import streamlit as st
from rest_client import RestServiceClient, ToolUpdate
from utils.async_utils import run_async


def show_tools_page(rest_client: RestServiceClient):
    """Display tools page with management functionality."""
    st.title("Инструменты")

    # Получаем список инструментов
    tools = run_async(rest_client.get_tools())

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

        # Отображаем таблицу и кнопки в колонках
        col1, col2 = st.columns([4, 1])

        with col1:
            st.dataframe(tools_df, hide_index=True, use_container_width=True)

        with col2:
            for tool in tools:
                if st.button("✏️", key=f"edit_{tool.id}", help="Редактировать"):
                    st.session_state["editing_tool"] = tool
                    st.rerun()

    # Секция редактирования инструмента
    if "editing_tool" in st.session_state:
        tool = st.session_state["editing_tool"]
        st.subheader(f"Редактировать инструмент: {tool.name}")

        with st.form("edit_tool_form"):
            new_description = st.text_area("Описание", value=tool.description)
            new_is_active = st.checkbox("Активен", value=tool.is_active)

            col1, col2 = st.columns(2)
            with col1:
                submit_button = st.form_submit_button("Обновить инструмент")
            with col2:
                cancel_button = st.form_submit_button("Отмена")

            if submit_button:
                with st.spinner("Обновляем инструмент..."):
                    updated_tool = ToolUpdate(
                        description=new_description,
                        is_active=new_is_active,
                    )
                    run_async(rest_client.update_tool(tool.id, updated_tool))
                    st.success(f"Инструмент {tool.name} успешно обновлен")
                    del st.session_state["editing_tool"]
                    st.rerun()

            if cancel_button:
                del st.session_state["editing_tool"]
                st.rerun()
