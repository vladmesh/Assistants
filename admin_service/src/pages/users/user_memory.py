"""User memory viewer page."""

import streamlit as st

from rest_client import RestServiceClient
from utils.async_utils import run_async


def show_user_memory_page(rest_client: RestServiceClient, user_id: int):
    """Display user memory (facts) page.

    Args:
        rest_client: REST service client
        user_id: User ID to show memory for
    """
    st.header(f"User Memory (ID: {user_id})")

    # Load memories
    memories = run_async(rest_client.get_user_memories(user_id))

    if not memories:
        st.info("No saved facts for this user")
        return

    st.write(f"Total facts: {len(memories)}")

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        search_query = st.text_input("Search by content")
    with col2:
        sort_by = st.selectbox("Sort by", ["Date (newest)", "Date (oldest)"])

    # Filter memories
    filtered = memories
    if search_query:
        filtered = [
            m
            for m in memories
            if search_query.lower() in (m.get("content") or "").lower()
        ]

    # Sort
    reverse = sort_by == "Date (newest)"
    filtered.sort(key=lambda x: x.get("created_at", ""), reverse=reverse)

    st.write(f"Showing: {len(filtered)} facts")
    st.divider()

    # Display memories
    for memory in filtered:
        content = memory.get("content", "")
        preview = content[:100] + "..." if len(content) > 100 else content
        memory_id = memory.get("id", "")

        with st.expander(f"{preview}"):
            st.write(f"**ID:** `{memory_id}`")
            st.write(f"**Created:** {memory.get('created_at', 'Unknown')}")
            st.write(f"**Source:** {memory.get('source', 'unknown')}")

            st.write("**Full Content:**")
            st.text_area(
                "Content",
                value=content,
                height=150,
                disabled=True,
                key=f"content_{memory_id}",
                label_visibility="collapsed",
            )

            # Delete button
            if st.button("Delete", key=f"delete_{memory_id}", type="secondary"):
                success = run_async(rest_client.delete_memory(memory_id))
                if success:
                    st.success("Memory deleted")
                    st.rerun()
                else:
                    st.error("Failed to delete memory")
