"""
Job scheduler - manages batch job execution.
"""

import logging
from collections.abc import Callable

import schedule

logger = logging.getLogger(__name__)


class JobScheduler:
    """
    Scheduler for batch jobs.
    """

    def __init__(self):
        """Initialize job scheduler."""
        self.scheduled_jobs = []
        logger.info("Initialized Job Scheduler")

    def schedule_daily_job(self, job_func: Callable, time: str, name: str = None) -> None:
        """
        Schedule a job to run daily at a specific time.

        Args:
            job_func: Function to run
            time: Time in HH:MM format (e.g., "02:00" for 2 AM)
            name: Optional job name
        """
        job_name = name or job_func.__name__
        logger.info(f"Scheduling daily job '{job_name}' at {time}")

        schedule.every().day.at(time).do(self._run_job, job_func, job_name)
        self.scheduled_jobs.append(
            {"name": job_name, "frequency": "daily", "time": time, "next_run": None}
        )

    def schedule_periodic_job(
        self, job_func: Callable, interval: int, unit: str = "hours", name: str = None
    ) -> None:
        """
        Schedule a job to run periodically.

        Args:
            job_func: Function to run
            interval: Interval value
            unit: "seconds", "minutes", "hours", "days"
            name: Optional job name
        """
        job_name = name or job_func.__name__
        logger.info(f"Scheduling periodic job '{job_name}' every {interval} {unit}")

        if unit == "seconds":
            schedule.every(interval).seconds.do(self._run_job, job_func, job_name)
        elif unit == "minutes":
            schedule.every(interval).minutes.do(self._run_job, job_func, job_name)
        elif unit == "hours":
            schedule.every(interval).hours.do(self._run_job, job_func, job_name)
        elif unit == "days":
            schedule.every(interval).days.do(self._run_job, job_func, job_name)

        self.scheduled_jobs.append(
            {"name": job_name, "frequency": f"every {interval} {unit}", "next_run": None}
        )

    def start(self) -> None:
        """Start the scheduler."""
        logger.info("Starting job scheduler")
        # TODO: Implement scheduler loop
        # Use schedule.run_pending() in a loop
        pass

    def stop(self) -> None:
        """Stop the scheduler."""
        logger.info("Stopping job scheduler")
        # TODO: Implement graceful shutdown

    def _run_job(self, job_func: Callable, job_name: str) -> None:
        """Run a job and log results."""
        logger.info(f"Running job: {job_name}")
        try:
            result = job_func()
            logger.info(f"Job '{job_name}' completed successfully")
            logger.debug(f"Job result: {result}")
        except Exception as e:
            logger.error(f"Job '{job_name}' failed: {str(e)}")

    def get_scheduled_jobs(self):
        """Get list of scheduled jobs."""
        return self.scheduled_jobs
