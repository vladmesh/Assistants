"""Main entry point for the admin panel"""

import streamlit as st
import streamlit_authenticator as stauth
from shared_models import configure_logging, get_logger

from config.settings import settings
from pages.assistants.assistants import show_assistants_page
from pages.monitoring.jobs import show_jobs_page
from pages.monitoring.logs import show_logs_page
from pages.monitoring.metrics import show_metrics_page
from pages.monitoring.queues import show_queues_page
from pages.system_settings.global_settings import show_global_settings_page
from pages.tools.tools import show_tools_page
from pages.users.users import show_users_page
from rest_client import RestServiceClient

# Configure page FIRST
st.set_page_config(
    page_title=settings.APP_TITLE,
    page_icon=settings.APP_ICON,
    layout=settings.APP_LAYOUT,
)

# Configure logging
configure_logging(
    service_name="admin_service",
    log_level=settings.LOG_LEVEL,
    json_format=settings.LOG_JSON_FORMAT,
)
logger = get_logger(__name__)

# Build authentication configuration from the environment.
# Secrets (cookie key, bcrypt password hash) never live in the repo; they are
# injected via env vars. The app refuses to start if either is missing.
if not settings.ADMIN_COOKIE_KEY or not settings.ADMIN_PASSWORD_HASH:
    st.error("ADMIN_COOKIE_KEY and ADMIN_PASSWORD_HASH must be set in the environment.")
    logger.error("Missing admin auth secrets; refusing to start.")
    st.stop()

credentials = {
    "usernames": {
        settings.ADMIN_USERNAME: {
            "email": settings.ADMIN_EMAIL,
            "name": settings.ADMIN_NAME,
            "password": settings.ADMIN_PASSWORD_HASH,
        }
    }
}

try:
    authenticator = stauth.Authenticate(
        credentials,
        settings.ADMIN_COOKIE_NAME,
        settings.ADMIN_COOKIE_KEY,
        settings.ADMIN_COOKIE_EXPIRY_DAYS,
        [],
    )
except Exception as e:
    st.error(f"Error initializing authenticator: {e}")
    logger.exception("Error initializing authenticator")
    st.stop()


# Initialize REST API client (moved here to avoid creation before authentication)
rest_client = RestServiceClient()

# ----- Authentication -----
# st.session_state.authentication_status can be:
# - None: If the user has not tried to log in
# - False: If the login attempt failed
# - True: If the user has successfully logged in
name, authentication_status, username = authenticator.login(location="main")


# Check authentication status safely using .get()
auth_status = st.session_state.get("authentication_status")

if auth_status is False:
    st.error("Username/password is incorrect")
elif auth_status is None:
    st.warning("Please enter your username and password")
elif auth_status is True:
    # ----- Main application (after successful login) -----
    # Use .get() for session state access as well
    user_name = st.session_state.get("name", "Admin")  # Provide a default name
    st.sidebar.title(f"Welcome *{user_name}*")
    authenticator.logout("Logout", "sidebar")  # Logout button in the sidebar

    # Sidebar navigation (filter out separator)
    nav_items = [item for item in settings.NAV_ITEMS if item != "---"]
    page = st.sidebar.radio("Навигация", nav_items)

    # Page routing
    if page == "Пользователи":
        show_users_page(rest_client)
    elif page == "Ассистенты":
        show_assistants_page(rest_client)
    elif page == "Инструменты":
        show_tools_page(rest_client)
    elif page == "Глобальные настройки":
        show_global_settings_page(rest_client)
    elif page == "Логи":
        show_logs_page()
    elif page == "Джобы":
        show_jobs_page(rest_client)
    elif page == "Очереди":
        show_queues_page(rest_client)
    elif page == "Метрики":
        show_metrics_page()
