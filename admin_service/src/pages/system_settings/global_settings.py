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
        "Could not import shared models. Ensure shared_models package is "
        "installed and accessible."
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
                key="global_prompt_input",
            )

        with col2:
            context_value = st.number_input(
                "Размер контекстного окна (токены):",
                value=settings.context_window_size,
                min_value=1,
                step=100,
                help="Максимальный размер контекстного окна для LLM.",
                key="global_context_input",
            )

        st.divider()

        # --- Memory V2 Settings ---
        st.subheader("Настройки Memory V2")

        mem_col1, mem_col2 = st.columns(2)

        with mem_col1:
            memory_retrieve_limit = st.number_input(
                "Количество memories для извлечения:",
                value=settings.memory_retrieve_limit,
                min_value=1,
                max_value=50,
                step=1,
                help="Количество релевантных воспоминаний для контекста.",
                key="memory_retrieve_limit",
            )
            memory_retrieve_threshold = st.slider(
                "Порог similarity для извлечения:",
                min_value=0.0,
                max_value=1.0,
                value=settings.memory_retrieve_threshold,
                step=0.05,
                help="Минимальный порог схожести для извлечения memories.",
                key="memory_retrieve_threshold",
            )

        with mem_col2:
            memory_dedup_threshold = st.slider(
                "Порог дедупликации:",
                min_value=0.0,
                max_value=1.0,
                value=settings.memory_dedup_threshold,
                step=0.05,
                help="Порог схожести для дедупликации фактов.",
                key="memory_dedup_threshold",
            )
            memory_update_threshold = st.slider(
                "Порог обновления:",
                min_value=0.0,
                max_value=1.0,
                value=settings.memory_update_threshold,
                step=0.05,
                help="Порог для обновления существующего факта.",
                key="memory_update_threshold",
            )

        st.divider()

        # --- Batch Extraction Settings ---
        st.subheader("Batch Extraction (Memory V2)")

        batch_col1, batch_col2 = st.columns(2)

        with batch_col1:
            memory_extraction_enabled = st.checkbox(
                "Включить автоматическое извлечение",
                value=settings.memory_extraction_enabled,
                help="Включить фоновое извлечение фактов из диалогов.",
                key="memory_extraction_enabled",
            )
            memory_extraction_interval = st.number_input(
                "Интервал извлечения (часы):",
                value=settings.memory_extraction_interval_hours,
                min_value=1,
                max_value=168,
                step=1,
                help="Как часто запускать batch extraction.",
                key="memory_extraction_interval",
            )

        with batch_col2:
            memory_extraction_model = st.text_input(
                "Модель для извлечения:",
                value=settings.memory_extraction_model,
                help="LLM модель для извлечения фактов (например, gpt-4o-mini).",
                key="memory_extraction_model",
            )
            memory_extraction_provider = st.selectbox(
                "Провайдер:",
                options=["openai", "google", "anthropic"],
                index=["openai", "google", "anthropic"].index(
                    settings.memory_extraction_provider
                ),
                help="Провайдер LLM для извлечения.",
                key="memory_extraction_provider",
            )

        st.divider()

        # --- Embedding Settings ---
        st.subheader("Настройки Embeddings")

        emb_col1, emb_col2 = st.columns(2)

        with emb_col1:
            embedding_model = st.text_input(
                "Модель embeddings:",
                value=settings.embedding_model,
                help="Модель для генерации embeddings.",
                key="embedding_model",
            )

        with emb_col2:
            embedding_provider = st.selectbox(
                "Провайдер embeddings:",
                options=["openai", "google", "anthropic"],
                index=["openai", "google", "anthropic"].index(
                    settings.embedding_provider
                ),
                help="Провайдер для embeddings.",
                key="embedding_provider",
            )

        st.divider()

        # --- Limits ---
        max_memories = st.number_input(
            "Максимум memories на пользователя:",
            value=settings.max_memories_per_user,
            min_value=1,
            max_value=10000,
            step=100,
            help="Максимальное количество memories для одного пользователя.",
            key="max_memories_per_user",
        )

        st.divider()

        # --- Save Button ---
        if st.button("Сохранить изменения", type="primary", key="global_save_button"):
            update_data = GlobalSettingsUpdate(
                summarization_prompt=prompt_value,
                context_window_size=context_value,
                # Memory V2
                memory_retrieve_limit=memory_retrieve_limit,
                memory_retrieve_threshold=memory_retrieve_threshold,
                memory_dedup_threshold=memory_dedup_threshold,
                memory_update_threshold=memory_update_threshold,
                # Batch Extraction
                memory_extraction_enabled=memory_extraction_enabled,
                memory_extraction_interval_hours=memory_extraction_interval,
                memory_extraction_model=memory_extraction_model,
                memory_extraction_provider=memory_extraction_provider,
                # Embeddings
                embedding_model=embedding_model,
                embedding_provider=embedding_provider,
                # Limits
                max_memories_per_user=max_memories,
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
                # Optional: Force rerun if needed, though state update should handle it
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
            "Не удалось загрузить настройки. Попробуйте обновить страницу или "
            "проверьте логи rest_service."
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
