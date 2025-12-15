"""Prometheus metrics for cron_service."""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Counters
jobs_total = Counter(
    "cron_jobs_total",
    "Total number of job executions",
    ["job_type", "status"],
)

# Gauges
scheduled_jobs = Gauge(
    "cron_scheduled_jobs",
    "Number of currently scheduled jobs",
    ["job_type"],
)

# Histograms
job_duration_seconds = Histogram(
    "cron_job_duration_seconds",
    "Job execution duration in seconds",
    ["job_type"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)


def record_job_completed(job_type: str, duration_seconds: float) -> None:
    """Record a completed job."""
    jobs_total.labels(job_type=job_type, status="completed").inc()
    job_duration_seconds.labels(job_type=job_type).observe(duration_seconds)


def record_job_failed(job_type: str) -> None:
    """Record a failed job."""
    jobs_total.labels(job_type=job_type, status="failed").inc()


def update_scheduled_jobs_count(job_type: str, count: int) -> None:
    """Update gauge for scheduled jobs count."""
    scheduled_jobs.labels(job_type=job_type).set(count)


def get_metrics() -> bytes:
    """Return metrics in Prometheus format."""
    return generate_latest()


def get_content_type() -> str:
    """Return Prometheus content type."""
    return CONTENT_TYPE_LATEST
