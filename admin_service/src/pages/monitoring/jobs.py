"""Cron jobs monitoring page."""

import pandas as pd
import streamlit as st

from rest_client import RestServiceClient
from utils.async_utils import run_async


def show_jobs_page(rest_client: RestServiceClient):
    """Display cron jobs monitoring page."""
    st.header("Cron Jobs")

    # Statistics
    stats = run_async(rest_client.get_job_stats(hours=24))
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total (24h)", stats.get("total", 0))
        col2.metric("Completed", stats.get("completed", 0))
        col3.metric("Failed", stats.get("failed", 0), delta_color="inverse")
        col4.metric("Running", stats.get("running", 0))

        avg_duration = stats.get("avg_duration_ms", 0)
        if avg_duration:
            st.caption(f"Avg duration: {avg_duration / 1000:.2f}s")

    st.divider()

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        job_type = st.selectbox(
            "Job Type",
            ["All", "reminder", "memory_extraction", "update_reminders"],
        )
    with col2:
        status_filter = st.selectbox(
            "Status",
            ["All", "scheduled", "running", "completed", "failed"],
        )
    with col3:
        hours = st.slider("Period (hours)", 1, 168, 24)

    # Build params
    params = {"hours": hours, "limit": 100}
    if job_type != "All":
        params["job_type"] = job_type
    if status_filter != "All":
        params["status"] = status_filter

    # Load data
    jobs = run_async(rest_client.get_job_executions(**params))

    if not jobs:
        st.info("No data for selected period")
        return

    # Create DataFrame
    df = pd.DataFrame(jobs)

    # Format columns
    if "scheduled_at" in df.columns:
        df["scheduled_at"] = pd.to_datetime(df["scheduled_at"])
    if "duration_ms" in df.columns:
        df["duration_sec"] = df["duration_ms"].apply(
            lambda x: f"{x / 1000:.2f}" if x else "-"
        )

    # Display table with status highlighting
    display_cols = ["job_name", "job_type", "status", "scheduled_at", "duration_sec"]
    if "error" in df.columns:
        display_cols.append("error")

    available_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[available_cols], use_container_width=True)

    st.divider()

    # Job details
    st.subheader("Job Details")
    if jobs:
        job_options = {
            f"{j.get('job_name', 'Unknown')} ({j.get('scheduled_at', '')[:19]})": j
            for j in jobs
        }
        selected_label = st.selectbox(
            "Select job for details", options=job_options.keys()
        )

        if selected_label:
            job = job_options[selected_label]
            with st.expander("Full Details", expanded=True):
                st.json(job)
