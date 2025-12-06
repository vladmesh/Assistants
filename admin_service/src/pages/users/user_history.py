import streamlit as st

from rest_client import RestServiceClient
from utils.async_utils import run_async


def render_user_history_page(user_id: int, rest_client: RestServiceClient):
    st.title("История пользователя")

    # Get messages
    st.subheader("Сообщения")
    messages = run_async(rest_client.get_messages(user_id=user_id))

    if not messages:
        st.info("Нет сообщений")
        return

    # Display messages in a table
    messages_data = []
    for msg in messages:
        messages_data.append(
            {
                "ID": msg.id,
                "Роль": msg.role,
                "Содержание": msg.content,
                "Тип": msg.content_type,
                "Статус": msg.status,
                "Время": msg.timestamp,
            }
        )

    st.dataframe(
        messages_data,
        column_config={
            "ID": st.column_config.NumberColumn("ID", width="small"),
            "Роль": st.column_config.TextColumn("Роль", width="small"),
            "Содержание": st.column_config.TextColumn("Содержание", width="large"),
            "Тип": st.column_config.TextColumn("Тип", width="small"),
            "Статус": st.column_config.TextColumn("Статус", width="small"),
            "Время": st.column_config.DatetimeColumn("Время", width="medium"),
        },
        hide_index=True,
    )
