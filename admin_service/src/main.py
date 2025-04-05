"""Main entry point for the admin panel"""

import logging

import streamlit as st
import structlog
from config.settings import settings
from pages.assistants import show_assistants_page
from pages.users import show_users_page
from rest_client import RestServiceClient

# Настройка логирования
logging.basicConfig(level=settings.LOG_LEVEL)
logger = structlog.get_logger()

# Инициализация клиента REST API
rest_client = RestServiceClient()

# Настройка страницы
st.set_page_config(
    page_title=settings.APP_TITLE,
    page_icon=settings.APP_ICON,
    layout=settings.APP_LAYOUT,
)

# Сайдбар с навигацией
page = st.sidebar.radio("Навигация", settings.NAV_ITEMS)

# Маршрутизация страниц
if page == settings.NAV_ITEMS[0]:  # Пользователи
    show_users_page(rest_client)
elif page == settings.NAV_ITEMS[1]:  # Ассистенты
    show_assistants_page(rest_client)
