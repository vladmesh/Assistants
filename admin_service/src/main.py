import asyncio
import logging
from typing import List

import streamlit as st
import structlog
from config import settings
from rest_client import RestServiceClient, User

# Настройка логирования
logging.basicConfig(level=settings.LOG_LEVEL)
logger = structlog.get_logger()

# Инициализация клиента REST API
rest_client = RestServiceClient()


async def get_users() -> List[User]:
    """Получить список пользователей из REST API."""
    try:
        return await rest_client.get_users()
    except Exception as e:
        logger.error("Ошибка при получении пользователей", error=str(e))
        st.error(f"Ошибка при получении пользователей: {str(e)}")
        return []


def main():
    """Основная функция приложения."""
    st.set_page_config(
        page_title="Admin Panel",
        page_icon="👨‍💼",
        layout="wide",
    )

    st.title("Admin Panel")
    st.sidebar.title("Navigation")

    # Получение списка пользователей
    users = asyncio.run(get_users())

    # Отображение списка пользователей
    st.header("Users")
    if users:
        # Создаем DataFrame для отображения
        import pandas as pd

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
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No users found.")


if __name__ == "__main__":
    main()
