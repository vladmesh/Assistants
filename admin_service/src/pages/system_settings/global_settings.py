"""Streamlit page for managing global system settings."""

import asyncio  # <-- Импортировать asyncio
import logging

import httpx  # Import httpx to catch potential request errors
import streamlit as st

# Assuming RestServiceClient is in the parent directory or src root
# Adjust the import path based on your project structure
try:
    from src.rest_client import RestServiceClient
except ImportError:
    # Fallback for running script directly? Or handle structure difference
    from rest_client import RestServiceClient

# Assuming shared_models is accessible
try:
    from shared_models.api_schemas.global_settings import (
        GlobalSettingsRead,
        GlobalSettingsUpdate,
    )
except ImportError:
    st.error(
        "Could not import shared models. Ensure shared_models package is installed and accessible."
    )
    st.stop()


logger = logging.getLogger(__name__)

# Key for session state
SESSION_STATE_KEY = "global_settings"


def show_global_settings_page(rest_client: RestServiceClient):
    """Renders the page for viewing and editing global settings."""
    st.title("Глобальные настройки системы")

    # --- Load settings ---
    if SESSION_STATE_KEY not in st.session_state:
        try:
            st.session_state[SESSION_STATE_KEY] = None  # Initialize
            with st.spinner("Загрузка настроек..."):
                # Запустить корутину с помощью asyncio.run()
                settings_data = asyncio.run(rest_client.get_global_settings())
                st.session_state[SESSION_STATE_KEY] = settings_data
        except httpx.RequestError as e:
            st.error(f"Ошибка сети при загрузке настроек: {e}")
            logger.error(f"Network error loading global settings: {e}", exc_info=True)
            # Keep None in session state to indicate loading failed
        except Exception as e:
            st.error(f"Не удалось загрузить глобальные настройки: {e}")
            logger.error(f"Failed to load global settings: {e}", exc_info=True)
            # Keep None in session state

    # --- Display and Edit Form ---
    settings: GlobalSettingsRead | None = st.session_state.get(SESSION_STATE_KEY)

    if settings:
        st.subheader("Параметры Ассистента")

        # Use columns for better layout
        col1, col2 = st.columns(2)

        with col1:
            prompt_value = st.text_area(
                "Промпт суммаризации:",
                value=settings.summarization_prompt,
                height=200,
                help="Промпт, используемый для суммирования истории диалога.",
                key="global_prompt_input",  # Add key for state management
            )

        with col2:
            context_value = st.number_input(
                "Размер контекстного окна (токены):",
                value=settings.context_window_size,
                min_value=1,
                step=100,  # Larger step for easier adjustment
                help="Максимальный размер контекстного окна для LLM.",
                key="global_context_input",  # Add key for state management
            )

        st.divider()

        # --- Save Button ---
        if st.button("Сохранить изменения", type="primary", key="global_save_button"):
            update_data = GlobalSettingsUpdate(
                summarization_prompt=prompt_value,
                context_window_size=context_value,
            )
            try:
                with st.spinner("Сохранение..."):
                    # Запустить корутину с помощью asyncio.run()
                    updated_settings = asyncio.run(
                        rest_client.update_global_settings(update_data)
                    )
                # Update session state with the *returned* data from API
                st.session_state[SESSION_STATE_KEY] = updated_settings
                st.success("Настройки успешно сохранены!")
                # Optional: Force immediate rerun if needed, though state update should handle it
                # st.experimental_rerun()
            except httpx.RequestError as e:
                st.error(f"Ошибка сети при сохранении настроек: {e}")
                logger.error(
                    f"Network error saving global settings: {e}", exc_info=True
                )
            except Exception as e:
                st.error(f"Не удалось сохранить настройки: {e}")
                logger.error(f"Failed to save global settings: {e}", exc_info=True)

    elif (
        st.session_state.get(SESSION_STATE_KEY) is None
        and SESSION_STATE_KEY in st.session_state
    ):
        # Explicitly check if loading failed (kept None in session state)
        st.warning(
            "Не удалось загрузить настройки. Попробуйте обновить страницу или проверьте логи rest_service."
        )
    # else: # Initial state before loading attempt - spinner is shown


# Example of how to run this page directly for testing (optional)
# if __name__ == "__main__":
#     # Mock or initialize RestServiceClient appropriately for standalone testing
#     # This requires handling potential async nature if client methods are async
#     # For simplicity, assuming synchronous client methods for direct run:
#     # client = RestServiceClient()
#     # show_global_settings_page(client)
#     st.info("Run main.py to see this page within the admin panel.")
