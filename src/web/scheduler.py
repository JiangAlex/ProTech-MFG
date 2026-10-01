"""Scheduler — APScheduler integration for timed test execution."""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import db

scheduler = AsyncIOScheduler()


def parse_cron(expr: str) -> dict:
    """Parse '0 2 * * *' into CronTrigger kwargs."""
    parts = expr.strip().split()
    if len(parts) == 5:
        return {"minute": parts[0], "hour": parts[1], "day": parts[2],
                "month": parts[3], "day_of_week": parts[4]}
    return {"minute": "0", "hour": "2"}


async def _run_scheduled_test(test_id: str):
    """Triggered by scheduler — run a test."""
    from runner import start_run
    await start_run(test_id)


def add_schedule(schedule_id: int, test_id: str, cron: str):
    """Add a job to the scheduler."""
    trigger = CronTrigger(**parse_cron(cron))
    scheduler.add_job(
        _run_scheduled_test,
        trigger=trigger,
        id=str(schedule_id),
        args=[test_id],
        replace_existing=True,
    )


def remove_schedule(schedule_id: int):
    """Remove a job from the scheduler."""
    try:
        scheduler.remove_job(str(schedule_id))
    except Exception:
        pass


def get_next_run(schedule_id: int) -> str:
    """Get next run time for a schedule."""
    try:
        job = scheduler.get_job(str(schedule_id))
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
    except Exception:
        pass
    return ""


def load_all_schedules():
    """Load all enabled schedules from DB into APScheduler."""
    for s in db.list_schedules():
        if s["enabled"]:
            add_schedule(s["id"], s["test_id"], s["cron"])


def start():
    """Start the scheduler and load existing schedules."""
    load_all_schedules()
    scheduler.start()
