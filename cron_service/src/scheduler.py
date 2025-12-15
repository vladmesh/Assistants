import asyncio
import time
import traceback
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from dateutil.parser import isoparse
from pytz import timezone as pytz_timezone
from pytz import utc
from shared_models import LogEventType, get_logger

import metrics
from redis_client import send_reminder_trigger
from rest_client import (
    complete_job_execution,
    create_job_execution,
    fail_job_execution,
    fetch_active_reminders,
    fetch_global_settings,
    mark_reminder_completed,
    start_job_execution,
)

logger = get_logger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 5  # секунды
JOB_ID_PREFIX = "reminder_"

# Создаем планировщик с явным указанием UTC
scheduler = BackgroundScheduler(timezone=utc)


def _job_func(reminder_data):
    """Function executed by the scheduler when a reminder triggers."""
    reminder_id = reminder_data.get("id", "unknown")
    reminder_type = reminder_data.get("type")
    user_id = reminder_data.get("user_id")
    job_id = f"{JOB_ID_PREFIX}{reminder_id}"
    start_time = time.perf_counter()

    # Create execution record
    execution = create_job_execution(
        job_id=job_id,
        job_name=f"Reminder {reminder_id}",
        job_type="reminder",
        scheduled_at=datetime.now(UTC),
        user_id=user_id,
        reminder_id=reminder_id if reminder_id != "unknown" else None,
    )
    execution_id = execution.get("id") if execution else None

    if execution_id:
        start_job_execution(execution_id)

    logger.info(
        "Job started",
        event_type=LogEventType.JOB_START,
        reminder_id=reminder_id,
        reminder_type=reminder_type,
        user_id=user_id,
        execution_id=execution_id,
    )

    try:
        send_reminder_trigger(reminder_data)
        logger.info(
            "Reminder trigger sent",
            event_type=LogEventType.JOB_END,
            reminder_id=reminder_id,
        )

        # Mark one-time reminders as completed after sending trigger
        if reminder_type == "one_time" and reminder_id != "unknown":
            logger.info(
                "Marking one-time reminder as completed",
                reminder_id=reminder_id,
            )
            try:
                success = mark_reminder_completed(reminder_id)
                if not success:
                    logger.warning(
                        "mark_reminder_completed returned False",
                        reminder_id=reminder_id,
                    )
            except Exception as api_exc:
                logger.error(
                    "Exception calling mark_reminder_completed",
                    event_type=LogEventType.ERROR,
                    reminder_id=reminder_id,
                    error=str(api_exc),
                )

        # Record success
        duration = time.perf_counter() - start_time
        if execution_id:
            complete_job_execution(execution_id)
        metrics.record_job_completed("reminder", duration)

    except Exception as e:
        logger.error(
            "Error executing job",
            event_type=LogEventType.JOB_ERROR,
            reminder_id=reminder_id,
            error=str(e),
            exc_info=True,
        )
        # Record failure
        if execution_id:
            fail_job_execution(execution_id, str(e), traceback.format_exc())
        metrics.record_job_failed("reminder")


def schedule_job(reminder):
    """Schedules or updates a single reminder job in APScheduler."""
    job_id = f"{JOB_ID_PREFIX}{reminder['id']}"
    existing_job = scheduler.get_job(job_id)

    # Remove job if status is not active (completed, cancelled, paused)
    if reminder.get("status") != "active":
        if existing_job:
            scheduler.remove_job(job_id)
            logger.info(
                f"Removed job {job_id} due to inactive status: {reminder.get('status')}"
            )
        return  # Don't schedule inactive reminders

    trigger = None
    trigger_args = {
        "args": [reminder],  # Pass the full reminder data to the job function
    }

    reminder_timezone = reminder.get("timezone")
    job_timezone = utc
    if reminder_timezone:
        try:
            job_timezone = pytz_timezone(reminder_timezone)
        except Exception:
            logger.warning(
                "Invalid timezone '%s' for reminder %s. Falling back to UTC.",
                reminder_timezone,
                reminder.get("id"),
            )
            job_timezone = utc

    try:
        if reminder["type"] == "one_time" and reminder.get("trigger_at"):
            run_date = isoparse(reminder["trigger_at"])
            # Ensure the datetime is timezone-aware (assuming UTC from API)
            if run_date.tzinfo is None:
                run_date = utc.localize(run_date)
            else:
                run_date = run_date.astimezone(utc)

            trigger = DateTrigger(run_date=run_date, timezone=utc)
            trigger_args["trigger"] = trigger
            trigger_args["name"] = f"One-time reminder {reminder['id']}"
            trigger_args["misfire_grace_time"] = (
                60 * 120
            )  # Allow 120 minutes grace period

        elif reminder["type"] == "recurring" and reminder.get("cron_expression"):
            cron_parts = reminder["cron_expression"].split()
            if len(cron_parts) != 5:
                raise ValueError(
                    "Invalid CRON expression for %s: %s",
                    job_id,
                    reminder["cron_expression"],
                )

            trigger = CronTrigger(
                minute=cron_parts[0],
                hour=cron_parts[1],
                day=cron_parts[2],
                month=cron_parts[3],
                day_of_week=cron_parts[4],
                timezone=job_timezone,
            )
            trigger_args["trigger"] = trigger
            trigger_args["name"] = f"Recurring reminder {reminder['id']}"
            trigger_args["misfire_grace_time"] = 60  # Allow 1 minute grace period

        else:
            logger.warning(
                "Invalid type or missing trigger info for reminder %s, skipping.",
                reminder["id"],
            )
            return

    except Exception as e:
        logger.error(f"Error creating trigger for reminder {reminder['id']}: {e}")
        return  # Skip scheduling if trigger creation fails

    # Add or modify the job
    if existing_job:
        # Check if trigger needs update (simple check, might need refinement)
        # For simplicity, we'll just reschedule. APScheduler handles updates.
        try:
            scheduler.reschedule_job(job_id, **trigger_args)
            logger.info(f"Rescheduled job {job_id}.")
        except Exception as e:
            logger.error(f"Error rescheduling job {job_id}: {e}")
    else:
        try:
            scheduler.add_job(_job_func, id=job_id, **trigger_args)
            logger.info(f"Added job {job_id} ({trigger_args['name']}).")
        except Exception as e:
            logger.error(f"Error adding job {job_id}: {e}")


def update_jobs_from_rest():
    """Fetch active reminders from REST and update scheduler."""
    retries = 0
    while retries < MAX_RETRIES:
        try:
            logger.info("Starting update of reminders from REST service...")
            # Use the updated function name
            reminders = fetch_active_reminders()
            logger.info(f"Fetched {len(reminders)} active reminders from REST service.")

            if reminders is None:  # Handle fetch failure returning None
                raise ConnectionError("Failed to fetch reminders from REST service.")

            active_reminder_ids = {f"{JOB_ID_PREFIX}{r['id']}" for r in reminders}
            current_scheduler_jobs = scheduler.get_jobs()

            # Remove jobs that are no longer active or present in the fetched list
            for job in current_scheduler_jobs:
                if (
                    job.id.startswith(JOB_ID_PREFIX)
                    and job.id not in active_reminder_ids
                ):
                    try:
                        scheduler.remove_job(job.id)
                        logger.info(
                            f"Removed job {job.id} as it's no longer active or present."
                        )
                    except Exception as e:
                        logger.error(f"Error removing job {job.id}: {e}")

            # Add or update jobs based on the fetched reminders
            for reminder in reminders:
                schedule_job(reminder)

            # Update metrics - count scheduled reminder jobs
            reminder_jobs = [
                j for j in scheduler.get_jobs() if j.id.startswith(JOB_ID_PREFIX)
            ]
            metrics.update_scheduled_jobs_count("reminder", len(reminder_jobs))

            logger.info("Finished updating reminders from REST service.")
            break  # Exit loop on success

        except Exception as e:
            retries += 1
            logger.error(
                "Error updating reminders (attempt %s/%s): %s",
                retries,
                MAX_RETRIES,
                e,
            )
            if retries < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Max retries updating reminders; service unstable.")
                # Decide if we should raise or continue trying later
                break  # Stop retrying for now


def _run_memory_extraction_sync():
    """Synchronous wrapper to run async memory extraction job."""
    # Lazy import to avoid loading heavy dependencies at module level
    import json

    from jobs.memory_extraction import run_memory_extraction

    start_time = time.perf_counter()

    # Create execution record
    execution = create_job_execution(
        job_id="memory_extraction",
        job_name="Memory Extraction",
        job_type="memory_extraction",
        scheduled_at=datetime.now(UTC),
    )
    execution_id = execution.get("id") if execution else None

    if execution_id:
        start_job_execution(execution_id)

    logger.info(
        "Starting memory extraction job...",
        event_type=LogEventType.JOB_START,
        execution_id=execution_id,
    )

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            stats = loop.run_until_complete(run_memory_extraction())
            logger.info(
                "Memory extraction completed: %d conversations, %d facts extracted",
                stats.get("conversations_processed", 0),
                stats.get("facts_extracted", 0),
                event_type=LogEventType.JOB_END,
            )

            # Record success
            duration = time.perf_counter() - start_time
            if execution_id:
                complete_job_execution(execution_id, json.dumps(stats))
            metrics.record_job_completed("memory_extraction", duration)

        finally:
            loop.close()
    except Exception as e:
        logger.error(
            "Memory extraction job failed: %s",
            e,
            exc_info=True,
            event_type=LogEventType.JOB_ERROR,
        )
        # Record failure
        if execution_id:
            fail_job_execution(execution_id, str(e), traceback.format_exc())
        metrics.record_job_failed("memory_extraction")


def _get_memory_extraction_interval_hours() -> int:
    """Get memory extraction interval from settings."""
    try:
        settings = fetch_global_settings()
        if settings:
            return settings.get("memory_extraction_interval_hours", 24)
    except Exception as e:
        logger.warning("Failed to fetch settings for interval", error=str(e))
    return 24


def start_scheduler():
    """Starts the background scheduler."""
    try:
        # Add the job to periodically update reminders from the REST service
        scheduler.add_job(
            update_jobs_from_rest,
            "interval",
            minutes=1,
            id="update_reminders_from_rest",
            name="Update Reminders",
            misfire_grace_time=30,
        )

        # Add memory extraction job
        extraction_interval = _get_memory_extraction_interval_hours()
        scheduler.add_job(
            _run_memory_extraction_sync,
            IntervalTrigger(hours=extraction_interval, timezone=utc),
            id="memory_extraction",
            name="Memory Extraction",
            misfire_grace_time=3600,  # 1 hour grace period
        )
        logger.info(
            "Scheduled memory extraction job",
            interval_hours=extraction_interval,
        )

        # Perform an initial update immediately on start
        update_jobs_from_rest()

        scheduler.start()
        logger.info("Scheduler started successfully.")

        # Keep the main thread alive
        while True:
            time.sleep(2)

    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutting down...")
        scheduler.shutdown()
        logger.info("Scheduler shut down gracefully.")
    except Exception as e:
        logger.critical(f"Failed to start scheduler: {e}", exc_info=True)
        scheduler.shutdown()
        raise
