"""Users page of the admin panel"""

import pandas as pd
import streamlit as st

from rest_client import RestServiceClient
from utils.async_utils import run_async

from .user_history import render_user_history_page


def show_users_page(rest_client: RestServiceClient):
    """Display users page with secretary assignment functionality."""
    st.title("Пользователи")

    # Получаем список пользователей и секретарей
    users_and_secretaries = run_async(rest_client.get_users_and_secretaries())
    users, secretary_assistants = users_and_secretaries

    if not users:
        st.warning("Нет доступных пользователей")
        return

    # Получаем информацию о привязанных секретарях для каждого пользователя
    user_secretaries = {}
    for user in users:
        secretary = run_async(rest_client.get_user_secretary(user.id))
        user_secretaries[user.id] = secretary

    # Отображаем таблицу пользователей
    users_df = pd.DataFrame(
        [
            {
                "ID": user.id,
                "Telegram ID": user.telegram_id,
                "Username": user.username or "Не указан",
                "Секретарь": user_secretaries[user.id].name
                if user_secretaries[user.id]
                else "Нет секретаря",
            }
            for user in users
        ]
    )
    st.dataframe(users_df)

    # Добавляем кнопку для просмотра истории
    selected_user_id = st.selectbox(
        "Выберите пользователя для просмотра истории",
        options=[user.id for user in users],
        format_func=lambda x: next(
            (
                f"{user.username or 'Без имени'} (ID: {user.telegram_id})"
                for user in users
                if user.id == x
            ),
            f"ID: {x}",
        ),
    )

    if selected_user_id:
        render_user_history_page(selected_user_id, rest_client)

    # Секция назначения секретаря
    with st.expander("➕ Назначить секретаря", expanded=False):
        # Выбор пользователя
        selected_user = st.selectbox(
            "Выберите пользователя",
            options=users,
            format_func=lambda x: f"{x.username or 'Без имени'} (ID: {x.telegram_id})",
        )

        if selected_user:
            # Выбор секретаря
            secretary_options = [None] + secretary_assistants
            selected_secretary = st.selectbox(
                "Выберите секретаря",
                options=secretary_options,
                format_func=lambda x: "Без секретаря"
                if x is None
                else f"{x.name} ({x.model})",
            )

            # Кнопка назначения
            if st.button("Назначить секретаря"):
                with st.spinner("Назначаем секретаря..."):
                    if selected_secretary:
                        run_async(
                            rest_client.set_user_secretary(
                                selected_user.id, selected_secretary.id
                            )
                        )
                        st.success(
                            "Секретарь назначен: "
                            f"{selected_secretary.name} -> "
                            f"{selected_user.username or selected_user.telegram_id}"
                        )
                    else:
                        # Если выбран None, то удаляем секретаря
                        run_async(
                            rest_client.set_user_secretary(selected_user.id, None)
                        )
                        st.success(
                            f"Секретарь удален у пользователя "
                            f"{selected_user.username or selected_user.telegram_id}"
                        )
