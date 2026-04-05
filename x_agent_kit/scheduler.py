from __future__ import annotations
from typing import Callable
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

class Scheduler:
    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler()

    def add(self, cron_expr: str, func: Callable) -> None:
        parts = cron_expr.split()
        if len(parts) == 5:
            trigger = CronTrigger(minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4])
        else:
            trigger = CronTrigger.from_crontab(cron_expr)
        self._scheduler.add_job(func, trigger)
        logger.info(f"Scheduled job: {cron_expr}")

    def start(self) -> None:
        self._scheduler.start()
        logger.info("Scheduler started")

    def stop(self) -> None:
        self._scheduler.shutdown()
        logger.info("Scheduler stopped")
