"""Metrics page with Grafana embedding."""

import streamlit as st

from config.settings import settings


def show_metrics_page():
    """Display metrics page with embedded Grafana dashboards."""
    st.header("Metrics")

    grafana_url = settings.GRAFANA_URL

    if not grafana_url:
        st.warning("Grafana URL not configured. Set GRAFANA_URL environment variable.")
        st.info(
            "To enable metrics visualization:\n"
            "1. Deploy Grafana (see monitoring/ directory)\n"
            "2. Set GRAFANA_URL in .env (e.g., http://localhost:3000)\n"
            "3. Configure Grafana to allow embedding (GF_SECURITY_ALLOW_EMBEDDING=true)"
        )
        return

    # Dashboard selector
    dashboard_options = {
        "Overview": "smart-assistant-overview",
        "Services": "smart-assistant-services",
        "Queues": "smart-assistant-queues",
        "Cron Jobs": "smart-assistant-cron-jobs",
    }

    selected_dashboard = st.selectbox("Dashboard", list(dashboard_options.keys()))
    dashboard_uid = dashboard_options[selected_dashboard]

    # Time range selector
    time_ranges = {
        "Last 15 minutes": "now-15m",
        "Last 1 hour": "now-1h",
        "Last 6 hours": "now-6h",
        "Last 24 hours": "now-24h",
        "Last 7 days": "now-7d",
    }
    selected_time = st.selectbox("Time Range", list(time_ranges.keys()))
    time_from = time_ranges[selected_time]

    # Build Grafana URL
    dashboard_url = (
        f"{grafana_url}/d/{dashboard_uid}?orgId=1&from={time_from}&to=now&kiosk=tv"
    )

    st.markdown(f"[Open in Grafana]({dashboard_url})")

    # Embed Grafana dashboard
    # Note: Requires GF_SECURITY_ALLOW_EMBEDDING=true in Grafana config
    try:
        st.components.v1.iframe(dashboard_url, height=800, scrolling=True)
    except Exception as e:
        st.error(f"Failed to embed Grafana dashboard: {e}")
        st.info(
            "Make sure Grafana allows embedding. "
            "Set GF_SECURITY_ALLOW_EMBEDDING=true in Grafana config."
        )

    st.divider()

    # Quick metrics overview (from REST API)
    st.subheader("Quick Stats")
    col1, col2 = st.columns(2)

    with col1:
        st.write("**Prometheus endpoints:**")
        st.code(
            "- rest_service: http://rest_service:8000/metrics\n"
            "- assistant_service: http://assistant_service:8080/metrics\n"
            "- cron_service: http://cron_service:8080/metrics"
        )

    with col2:
        st.write("**Direct links:**")
        st.markdown(
            f"- [Prometheus]({settings.PROMETHEUS_URL or 'http://localhost:9090'})"
        )
        st.markdown(f"- [Grafana]({grafana_url})")
        st.markdown(f"- [Loki]({settings.LOKI_URL or 'http://localhost:3100'})")
