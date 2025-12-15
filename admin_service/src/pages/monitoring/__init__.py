"""Monitoring pages for admin panel."""

from .jobs import show_jobs_page
from .logs import show_logs_page
from .metrics import show_metrics_page
from .queues import show_queues_page

__all__ = [
    "show_jobs_page",
    "show_logs_page",
    "show_metrics_page",
    "show_queues_page",
]
