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
