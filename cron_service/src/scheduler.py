import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from dateutil.parser import isoparse  # For parsing ISO 8601 datetime strings
from pytz import utc

# Change back to absolute imports (without src.)
from redis_client import send_reminder_trigger
from rest_client import fetch_active_reminders, mark_reminder_completed

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 5  # секунды
JOB_ID_PREFIX = "reminder_"

# Создаем планировщик с явным указанием UTC
scheduler = BackgroundScheduler(timezone=utc)


def _job_func(reminder_data):
    """Function executed by the scheduler when a reminder triggers."""
    logger.info("--- ENTERING _job_func ---")
    reminder_id = reminder_data.get("id", "unknown")
    reminder_type = reminder_data.get("type")
    logger.info(f"_job_func started for reminder ID: {reminder_id}")
    try:
        logger.info(f"Executing job for reminder ID: {reminder_id}")
        logger.info(
            f"--- BEFORE Calling send_reminder_trigger for ID: {reminder_id} ---"
        )
        send_reminder_trigger(reminder_data)
        logger.info(f"Successfully sent trigger for reminder ID: {reminder_id}")

        # Mark one-time reminders as completed after sending trigger
        if reminder_type == "one_time" and reminder_id != "unknown":
            logger.info(
                f"Attempting to mark one-time reminder {reminder_id} as completed."
            )
            try:
                success = mark_reminder_completed(reminder_id)
                if not success:
                    logger.warning(
                        f"Call to mark_reminder_completed for {reminder_id} returned False."
                    )
            except Exception as api_exc:
                logger.error(
                    f"Exception calling mark_reminder_completed for {reminder_id}: {api_exc}"
                )

    except Exception as e:
        logger.error(
            f"Error executing job for reminder ID {reminder_id}: {e}", exc_info=True
        )
        # Consider adding retry logic here if needed
    logger.info(f"_job_func finished for reminder ID: {reminder_id}")


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
        "timezone": utc,
        "args": [reminder],  # Pass the full reminder data to the job function
    }

    try:
        if reminder["type"] == "one_time" and reminder.get("trigger_at"):
            run_date = isoparse(reminder["trigger_at"])
            # Ensure the datetime is timezone-aware (assuming UTC from API)
            if run_date.tzinfo is None:
                run_date = utc.localize(run_date)
            else:
                run_date = run_date.astimezone(utc)

            trigger = DateTrigger(run_date=run_date)
            trigger_args["trigger"] = trigger
            trigger_args["name"] = f"One-time reminder {reminder['id']}"
            trigger_args["misfire_grace_time"] = 60 * 5  # Allow 5 minutes grace period

        elif reminder["type"] == "recurring" and reminder.get("cron_expression"):
            cron_parts = reminder["cron_expression"].split()
            if len(cron_parts) != 5:
                raise ValueError(
                    f"Invalid CRON expression for {job_id}: {reminder['cron_expression']}"
                )

            trigger = CronTrigger(
                minute=cron_parts[0],
                hour=cron_parts[1],
                day=cron_parts[2],
                month=cron_parts[3],
                day_of_week=cron_parts[4],
                timezone=utc,
            )
            trigger_args["trigger"] = trigger
            trigger_args["name"] = f"Recurring reminder {reminder['id']}"
            trigger_args["misfire_grace_time"] = 60  # Allow 1 minute grace period

        else:
            logger.warning(
                f"Invalid type or missing trigger info for reminder {reminder['id']}, skipping."
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
    """Updates jobs in the scheduler by fetching active reminders from the REST service."""
    retries = 0
    while retries < MAX_RETRIES:
        try:
            logger.info("Starting update of reminders from REST service...")
            # Use the updated function name
            reminders = fetch_active_reminders()
            logger.info(f"Fetched {len(reminders)} active reminders from REST service.")

            if (
                reminders is None
            ):  # Handle case where fetch failed and returned None (or check for empty list if appropriate)
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

            logger.info("Finished updating reminders from REST service.")
            break  # Exit loop on success

        except Exception as e:
            retries += 1
            logger.error(
                f"Error updating reminders (attempt {retries}/{MAX_RETRIES}): {e}"
            )
            if retries < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(
                    "Max retries reached for updating reminders. Service might be unstable."
                )
                # Decide if we should raise or continue trying later
                break  # Stop retrying for now


def start_scheduler():
    """Starts the background scheduler."""
    try:
        # Add the job to periodically update reminders from the REST service
        scheduler.add_job(
            update_jobs_from_rest,
            "interval",
            minutes=1,  # Check for updates every minute
            id="update_reminders_from_rest",
            name="Update Reminders",
            misfire_grace_time=30,  # Allow 30 seconds grace period if update job misses schedule
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
        scheduler.shutdown()  # Attempt graceful shutdown on error
        raise
