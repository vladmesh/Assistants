"""Main entry point for the admin panel"""

from pathlib import Path

import streamlit as st
import streamlit_authenticator as stauth
import yaml
from shared_models import configure_logging, get_logger
from yaml.loader import SafeLoader

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

# Load authentication configuration
config_path = Path(__file__).parent / "config" / "credentials.yaml"
try:
    with config_path.open() as file:
        config = yaml.load(file, Loader=SafeLoader)
    # Ensure config is a dictionary
    if not isinstance(config, dict):
        config = {}
        st.error("Credentials configuration is invalid.")
        logger.error("Credentials configuration is not a valid dictionary.")
        st.stop()

except FileNotFoundError:
    st.error(f"Credentials file not found at {config_path}")
    logger.error(f"Credentials file not found at {config_path}")
    st.stop()  # Stop execution if config is missing
except yaml.YAMLError as e:
    st.error(f"Error parsing credentials configuration file: {e}")
    logger.exception("Error parsing credentials YAML file")
    st.stop()
except Exception as e:
    st.error(f"Error loading credentials configuration: {e}")
    logger.exception("Error loading credentials configuration")
    st.stop()


# Initialize authenticator
try:
    # Use .get for safer access and provide defaults
    credentials = config.get("credentials", {})
    cookie_config = config.get("cookie", {})
    preauthorized_config = config.get("preauthorized", {})

    authenticator = stauth.Authenticate(
        credentials,
        cookie_config.get("name", "admin_cookie"),  # Default name
        cookie_config.get(
            "key", "default_secret_key"
        ),  # Default key (consider logging a warning if default is used)
        cookie_config.get("expiry_days", 30),
        preauthorized_config.get("emails", []),
    )
    # Log a warning if the default cookie key is used
    if cookie_config.get("key") == "default_secret_key":
        logger.warning(
            "Using default cookie secret key. "
            "Please set a secure key in credentials.yaml."
        )

except KeyError as e:
    st.error(f"Missing key in credentials configuration: {e}")
    logger.exception(f"Missing key in credentials configuration: {e}")
    st.stop()
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
