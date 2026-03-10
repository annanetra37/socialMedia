"""
DailyScheduler — wraps APScheduler to run the four daily blocks
on a fixed schedule. Can be enabled/disabled via the API.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False


def _run_block(brand: dict, cycle: str) -> None:
    """Called by APScheduler — imports lazily to avoid circular imports."""
    from orchestrator.orchestrator import Orchestrator
    try:
        orch = Orchestrator(brand)
        if cycle == "monitoring":
            orch.run_monitoring_block()
        elif cycle == "engagement":
            orch.run_engagement_block()
        elif cycle == "content":
            orch.run_content_block(week=_current_week())
        elif cycle == "growth":
            orch.run_growth_block(week=_current_week())
    except Exception as exc:
        print(f"[scheduler] Error in {cycle} block: {exc}")


def _current_week() -> int:
    """Return the current week of the month (1-4)."""
    day = datetime.now().day
    return min((day - 1) // 7 + 1, 4)


class DailyScheduler:
    def __init__(self):
        self._scheduler: Optional[object] = None
        self._enabled = False
        self._config: dict = {}

    def enable(
        self,
        brand: dict,
        monitoring_time: str = "07:00",
        engagement_time: str = "08:00",
        content_time: str = "09:00",
        growth_time: str = "17:00",
        timezone: str = "UTC",
    ) -> None:
        if not HAS_APSCHEDULER:
            self._enabled = False
            return

        # Stop existing scheduler if running
        self.disable()

        sched = BackgroundScheduler(timezone=timezone)

        def _parse(t: str):
            h, m = t.split(":")
            return int(h), int(m)

        for cycle, time_str in [
            ("monitoring", monitoring_time),
            ("engagement", engagement_time),
            ("content", content_time),
            ("growth", growth_time),
        ]:
            h, m = _parse(time_str)
            sched.add_job(
                _run_block,
                trigger=CronTrigger(hour=h, minute=m),
                args=[brand, cycle],
                id=f"daily_{cycle}",
                replace_existing=True,
            )

        sched.start()
        self._scheduler = sched
        self._enabled = True
        self._config = {
            "brand": brand.get("name"),
            "monitoring_time": monitoring_time,
            "engagement_time": engagement_time,
            "content_time": content_time,
            "growth_time": growth_time,
            "timezone": timezone,
        }

    def disable(self) -> None:
        if self._scheduler and HAS_APSCHEDULER:
            try:
                self._scheduler.shutdown(wait=False)
            except Exception:
                pass
        self._scheduler = None
        self._enabled = False

    def get_status(self) -> dict:
        jobs = []
        if self._scheduler and HAS_APSCHEDULER and self._enabled:
            for job in self._scheduler.get_jobs():
                next_run = job.next_run_time
                jobs.append({
                    "id": job.id,
                    "next_run": next_run.isoformat() if next_run else None,
                })
        return {
            "enabled": self._enabled,
            "apscheduler_available": HAS_APSCHEDULER,
            "config": self._config,
            "jobs": jobs,
        }
