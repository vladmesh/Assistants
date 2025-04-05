"""Utilities for working with async code in Streamlit"""

import asyncio

import streamlit as st


def get_event_loop():
    """Get or create event loop for current Streamlit session."""
    if "loop" not in st.session_state:
        st.session_state.loop = asyncio.new_event_loop()
    return st.session_state.loop


def run_async(coro):
    """Safely run async coroutines in Streamlit."""
    loop = get_event_loop()
    return loop.run_until_complete(coro)
