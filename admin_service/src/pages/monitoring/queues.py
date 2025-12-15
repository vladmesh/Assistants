"""Redis queue monitoring page."""

import streamlit as st

from rest_client import RestServiceClient
from utils.async_utils import run_async


def show_queues_page(rest_client: RestServiceClient):
    """Display Redis queue monitoring page."""
    st.header("Message Queues")

    # Queue statistics
    stats = run_async(rest_client.get_queue_stats())

    if stats:
        for queue_stat in stats:
            queue_name = queue_stat.get("queue_name", "unknown")
            with st.expander(f"Queue: {queue_name}", expanded=True):
                col1, col2, col3 = st.columns(3)
                col1.metric("Total", queue_stat.get("total_messages", 0))
                col2.metric("Last Hour", queue_stat.get("messages_last_hour", 0))
                col3.metric("Last 24h", queue_stat.get("messages_last_24h", 0))

                by_type = queue_stat.get("by_type", {})
                if by_type:
                    st.write("**By Type:**")
                    st.bar_chart(by_type)

                by_source = queue_stat.get("by_source", {})
                if by_source:
                    st.write("**By Source:**")
                    st.bar_chart(by_source)
    else:
        st.info("No queue statistics available")

    st.divider()

    # Message history
    st.subheader("Message History")

    col1, col2, col3 = st.columns(3)
    with col1:
        queue_filter = st.selectbox("Queue", ["All", "to_secretary", "to_telegram"])
    with col2:
        user_filter = st.text_input("User ID")
    with col3:
        hours = st.slider("Period (hours)", 1, 48, 24, key="queue_hours")

    # Build params
    params = {"hours": hours, "limit": 50}
    if queue_filter != "All":
        params["queue_name"] = queue_filter
    if user_filter:
        try:
            params["user_id"] = int(user_filter)
        except ValueError:
            st.warning("User ID must be a number")

    # Load messages
    messages = run_async(rest_client.get_queue_messages(**params))

    if messages:
        for msg in messages:
            created_at = msg.get("created_at", "")[:19] if msg.get("created_at") else ""
            queue_name = msg.get("queue_name", "unknown")
            message_type = msg.get("message_type", "unknown")

            with st.expander(f"{created_at} | {queue_name} | {message_type}"):
                st.write(f"**User ID:** {msg.get('user_id')}")
                st.write(f"**Correlation ID:** {msg.get('correlation_id')}")
                st.write(f"**Source:** {msg.get('source')}")
                st.write(f"**Processed:** {msg.get('processed')}")

                payload = msg.get("payload")
                if payload:
                    st.write("**Payload:**")
                    try:
                        import json

                        st.json(json.loads(payload))
                    except (json.JSONDecodeError, TypeError):
                        st.code(payload)
    else:
        st.info("No messages for selected period")
