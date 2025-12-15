"""Logs viewer page with Grafana/Loki integration."""

from urllib.parse import quote

import streamlit as st

from config.settings import settings


def show_logs_page():
    """Display logs viewer page with Grafana Explore embedding."""
    st.header("Logs")

    grafana_url = settings.GRAFANA_URL

    if not grafana_url:
        st.warning("Grafana URL not configured. Set GRAFANA_URL environment variable.")
        st.info(
            "To enable log visualization:\n"
            "1. Deploy Loki and Grafana (see monitoring/ directory)\n"
            "2. Set GRAFANA_URL in .env\n"
            "3. Configure Promtail to collect Docker logs"
        )
        return

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        service = st.selectbox(
            "Service",
            [
                "All",
                "assistant_service",
                "rest_service",
                "telegram_bot_service",
                "cron_service",
                "google_calendar_service",
                "rag_service",
                "admin_service",
            ],
        )
    with col2:
        level = st.selectbox("Level", ["All", "error", "warning", "info", "debug"])
    with col3:
        time_range = st.selectbox(
            "Time Range",
            ["Last 15 minutes", "Last 1 hour", "Last 6 hours", "Last 24 hours"],
        )

    # Additional filters
    col1, col2 = st.columns(2)
    with col1:
        user_id_filter = st.text_input("User ID")
    with col2:
        correlation_id_filter = st.text_input("Correlation ID")

    # Build LogQL query
    filters = []
    if service != "All":
        filters.append(f'service="{service}"')
    if level != "All":
        filters.append(f'level="{level}"')

    logql = "{" + ",".join(filters) + "}" if filters else '{job="docker"}'

    # Add line filters
    line_filters = []
    if user_id_filter:
        line_filters.append('|= "user_id"')
        line_filters.append(f'|~ "user_id.*{user_id_filter}"')
    if correlation_id_filter:
        line_filters.append(f'|= "{correlation_id_filter}"')

    if line_filters:
        logql += " " + " ".join(line_filters)

    # Time range mapping
    time_map = {
        "Last 15 minutes": "now-15m",
        "Last 1 hour": "now-1h",
        "Last 6 hours": "now-6h",
        "Last 24 hours": "now-24h",
    }

    # Show generated query
    with st.expander("LogQL Query"):
        st.code(logql, language="logql")

    # Build Grafana Explore URL
    time_from = time_map[time_range]
    encoded_query = quote(logql)

    explore_url = (
        f"{grafana_url}/explore?"
        f"orgId=1&left="
        f'%7B"datasource":"Loki",'
        f'"queries":%5B%7B"expr":"{encoded_query}"%7D%5D,'
        f'"range":%7B"from":"{time_from}","to":"now"%7D%7D'
    )

    st.markdown(f"[Open in Grafana Explore]({explore_url})")

    # Embed Grafana Explore
    try:
        st.components.v1.iframe(explore_url, height=700, scrolling=True)
    except Exception as e:
        st.error(f"Failed to embed Grafana: {e}")

    st.divider()

    # Quick links
    st.subheader("Quick Filters")
    quick_filters = {
        "All Errors": '{level="error"}',
        "Assistant Service": '{service="assistant_service"}',
        "LLM Calls": '{event_type="llm_call"}',
        "Tool Calls": '{event_type="tool_call"}',
        "Job Errors": '{event_type="job_error"}',
        "Queue Activity": '{event_type=~"queue_push|queue_pop"}',
    }

    cols = st.columns(3)
    for i, (name, query) in enumerate(quick_filters.items()):
        encoded = quote(query)
        url = (
            f"{grafana_url}/explore?"
            f"orgId=1&left="
            f'%7B"datasource":"Loki",'
            f'"queries":%5B%7B"expr":"{encoded}"%7D%5D,'
            f'"range":%7B"from":"now-1h","to":"now"%7D%7D'
        )
        cols[i % 3].markdown(f"[{name}]({url})")
