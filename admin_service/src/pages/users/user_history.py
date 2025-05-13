from typing import List, Optional
from uuid import UUID

import streamlit as st
from rest_client import RestServiceClient
from utils.async_utils import run_async

from shared_models.api_schemas.message import MessageRead
from shared_models.api_schemas.user_summary import (
    UserSummaryCreateUpdate,
    UserSummaryRead,
)


def render_user_history_page(user_id: int, rest_client: RestServiceClient):
    st.title("История пользователя")

    # Get user summaries
    summaries = run_async(rest_client.get_user_summaries(user_id=user_id))

    # Display summaries if they exist
    st.subheader("Саммари")

    # Add new summary button
    with st.expander("➕ Добавить новое саммари", expanded=False):
        new_summary_text = st.text_area(
            "Текст саммари",
            key="new_summary_text",
            height=200,
        )

        # Get list of assistants for selection
        assistants = run_async(rest_client.get_assistants())
        assistant_options = {a.name: a.id for a in assistants}

        selected_assistant = st.selectbox(
            "Выберите ассистента",
            options=list(assistant_options.keys()),
            format_func=lambda x: x,
        )

        if st.button("Создать саммари"):
            if not new_summary_text:
                st.error("Введите текст саммари")
            else:
                try:
                    summary_data = UserSummaryCreateUpdate(
                        user_id=user_id,
                        assistant_id=assistant_options[selected_assistant],
                        summary_text=new_summary_text,
                    )
                    created_summary = run_async(
                        rest_client.create_user_summary(summary_data)
                    )
                    if created_summary:
                        st.success("Саммари создано")
                        st.rerun()
                    else:
                        st.error("Ошибка при создании саммари")
                except Exception as e:
                    st.error(f"Ошибка при создании саммари: {e}")

    if summaries:
        for summary in summaries:
            with st.expander(f"Саммари от {summary.created_at}"):
                # Allow editing summary
                new_summary = st.text_area(
                    "Текст саммари",
                    value=summary.summary_text,
                    key=f"summary_{summary.id}",
                )

                col1, col2 = st.columns(2)

                with col1:
                    if new_summary != summary.summary_text:
                        if st.button("Сохранить изменения", key=f"save_{summary.id}"):
                            try:
                                updated_summary = run_async(
                                    rest_client.update_user_summary(
                                        summary_id=summary.id,
                                        summary_data=UserSummaryCreateUpdate(
                                            user_id=user_id,
                                            assistant_id=summary.assistant_id,
                                            summary_text=new_summary,
                                            last_message_id_covered=summary.last_message_id_covered,
                                            token_count=summary.token_count,
                                        ),
                                    )
                                )
                                st.success("Саммари обновлено")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Ошибка при обновлении саммари: {e}")

                with col2:
                    if st.button("Удалить", key=f"delete_{summary.id}"):
                        try:
                            if run_async(rest_client.delete_user_summary(summary.id)):
                                st.success("Саммари удалено")
                                st.rerun()
                            else:
                                st.error("Ошибка при удалении саммари")
                        except Exception as e:
                            st.error(f"Ошибка при удалении саммари: {e}")

                # Display summary metadata
                st.write(f"ID: {summary.id}")
                st.write(f"Ассистент ID: {summary.assistant_id}")
                st.write(f"Последнее сообщение: {summary.last_message_id_covered}")
                st.write(f"Количество токенов: {summary.token_count}")
    else:
        st.info("У пользователя нет саммари")

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
                "Саммари ID": msg.summary_id,
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
            "Саммари ID": st.column_config.NumberColumn("Саммари ID", width="small"),
        },
        hide_index=True,
    )
