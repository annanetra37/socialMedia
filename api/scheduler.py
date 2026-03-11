"""
AgencyScheduler — multi-brand APScheduler wrapper.

Each brand can register its own four daily blocks at custom times.
All brands run in parallel via a single BackgroundScheduler instance.

Usage:
    scheduler = AgencyScheduler()
    scheduler.enable_brand(brand_profile, config)   # add / update one brand
    scheduler.disable_brand(brand_slug)             # remove one brand
    scheduler.disable_all()                         # stop everything
    scheduler.get_status()                          # all brands + job list
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False

from config.settings import STORAGE_DIR


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _current_week() -> int:
    """Week-of-month (1-4) based on current day."""
    return min((datetime.now().day - 1) // 7 + 1, 4)


def _save_brand_schedule(brand_slug: str, config: dict) -> None:
    """Persist a brand's schedule config so it survives restarts."""
    path = STORAGE_DIR / brand_slug / "schedule_config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2))


def _load_brand_schedule(brand_slug: str) -> Optional[dict]:
    path = STORAGE_DIR / brand_slug / "schedule_config.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def _delete_brand_schedule(brand_slug: str) -> None:
    path = STORAGE_DIR / brand_slug / "schedule_config.json"
    if path.exists():
        path.unlink()


def _load_all_brand_schedules() -> list[dict]:
    """Load all persisted schedule configs (for restart recovery)."""
    configs = []
    if STORAGE_DIR.exists():
        for brand_dir in STORAGE_DIR.iterdir():
            cfg_path = brand_dir / "schedule_config.json"
            if cfg_path.exists():
                try:
                    configs.append(json.loads(cfg_path.read_text()))
                except Exception:
                    pass
    return configs


# ── Job runner (called by APScheduler) ────────────────────────────────────────

def _run_brand_block(brand_profile: dict, cycle: str, log_fn=None) -> None:
    """Execute one block for one brand. Imported lazily to avoid circular imports."""
    from orchestrator.orchestrator import Orchestrator
    brand_name = brand_profile.get("name", "unknown")
    try:
        if log_fn:
            log_fn(f"[scheduler] {brand_name} — starting {cycle} block")
        orch = Orchestrator(brand_profile)
        week = _current_week()
        if cycle == "monitoring":
            orch.run_monitoring_block()
        elif cycle == "engagement":
            orch.run_engagement_block()
        elif cycle == "content":
            orch.run_content_block(week=week)
        elif cycle == "growth":
            orch.run_growth_block(week=week)
        if log_fn:
            log_fn(f"[scheduler] {brand_name} — {cycle} block complete")
    except Exception as exc:
        msg = f"[scheduler] ERROR {brand_name} {cycle}: {exc}"
        print(msg)
        if log_fn:
            log_fn(msg)


# ── Main class ────────────────────────────────────────────────────────────────

class AgencyScheduler:
    """
    Manages APScheduler jobs for any number of brands.
    Each brand gets 4 cron jobs (one per daily block).
    """

    def __init__(self):
        self._scheduler: Optional[object] = None
        self._started = False
        # brand_slug → config dict
        self._brands: dict[str, dict] = {}
        # brand_slug → last error string
        self._errors: dict[str, str] = {}

        if HAS_APSCHEDULER:
            self._scheduler = BackgroundScheduler()
            self._scheduler.start()
            self._started = True
            self._restore_from_disk()

    # ── Public API ────────────────────────────────────────────────────────────

    def enable_brand(
        self,
        brand_profile: dict,
        monitoring_time: str = "07:00",
        engagement_time: str = "08:00",
        content_time: str = "09:00",
        growth_time: str = "17:00",
        timezone: str = "UTC",
    ) -> dict:
        """Register (or update) the four daily blocks for a brand."""
        if not HAS_APSCHEDULER:
            return {"ok": False, "reason": "apscheduler not installed"}

        slug = _slug(brand_profile.get("name", "brand"))
        config = {
            "brand_slug": slug,
            "brand_name": brand_profile.get("name"),
            "brand_profile": brand_profile,
            "monitoring_time": monitoring_time,
            "engagement_time": engagement_time,
            "content_time": content_time,
            "growth_time": growth_time,
            "timezone": timezone,
            "enabled_at": datetime.now().isoformat(),
        }

        self._remove_brand_jobs(slug)

        for cycle, time_str in [
            ("monitoring", monitoring_time),
            ("engagement", engagement_time),
            ("content",    content_time),
            ("growth",     growth_time),
        ]:
            h, m = map(int, time_str.split(":"))
            job_id = f"{slug}__{cycle}"
            self._scheduler.add_job(
                _run_brand_block,
                trigger=CronTrigger(hour=h, minute=m, timezone=timezone),
                args=[brand_profile, cycle],
                id=job_id,
                replace_existing=True,
            )

        self._brands[slug] = config
        _save_brand_schedule(slug, config)
        return {"ok": True, "slug": slug, "jobs": self._brand_job_info(slug)}

    def disable_brand(self, brand_slug: str) -> None:
        """Remove all scheduled jobs for a brand."""
        self._remove_brand_jobs(brand_slug)
        self._brands.pop(brand_slug, None)
        _delete_brand_schedule(brand_slug)

    def disable_all(self) -> None:
        """Remove every scheduled job across all brands."""
        for slug in list(self._brands.keys()):
            self.disable_brand(slug)

    def get_status(self) -> dict:
        """Return full status: global state + per-brand info."""
        brands_status = []
        for slug, cfg in self._brands.items():
            brands_status.append({
                "brand_slug": slug,
                "brand_name": cfg.get("brand_name"),
                "timezone": cfg.get("timezone"),
                "times": {
                    "monitoring": cfg.get("monitoring_time"),
                    "engagement": cfg.get("engagement_time"),
                    "content":    cfg.get("content_time"),
                    "growth":     cfg.get("growth_time"),
                },
                "jobs": self._brand_job_info(slug),
                "last_error": self._errors.get(slug),
                "enabled_at": cfg.get("enabled_at"),
            })
        return {
            "active": self._started and HAS_APSCHEDULER,
            "apscheduler_available": HAS_APSCHEDULER,
            "total_brands": len(self._brands),
            "brands": brands_status,
        }

    def get_brand_status(self, brand_slug: str) -> Optional[dict]:
        cfg = self._brands.get(brand_slug)
        if not cfg:
            return None
        return {
            "brand_slug": brand_slug,
            "brand_name": cfg.get("brand_name"),
            "timezone": cfg.get("timezone"),
            "times": {
                "monitoring": cfg.get("monitoring_time"),
                "engagement": cfg.get("engagement_time"),
                "content":    cfg.get("content_time"),
                "growth":     cfg.get("growth_time"),
            },
            "jobs": self._brand_job_info(brand_slug),
            "enabled_at": cfg.get("enabled_at"),
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _remove_brand_jobs(self, brand_slug: str) -> None:
        if not HAS_APSCHEDULER or not self._scheduler:
            return
        for cycle in ("monitoring", "engagement", "content", "growth"):
            job_id = f"{brand_slug}__{cycle}"
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass

    def _brand_job_info(self, brand_slug: str) -> list[dict]:
        if not HAS_APSCHEDULER or not self._scheduler:
            return []
        jobs = []
        for cycle in ("monitoring", "engagement", "content", "growth"):
            job_id = f"{brand_slug}__{cycle}"
            try:
                job = self._scheduler.get_job(job_id)
                if job:
                    nxt = job.next_run_time
                    jobs.append({
                        "id": job_id,
                        "cycle": cycle,
                        "next_run": nxt.isoformat() if nxt else None,
                    })
            except Exception:
                pass
        return jobs

    def _restore_from_disk(self) -> None:
        """Re-register all brands whose schedule config was saved previously."""
        for cfg in _load_all_brand_schedules():
            brand_profile = cfg.get("brand_profile")
            if not brand_profile:
                continue
            try:
                self.enable_brand(
                    brand_profile=brand_profile,
                    monitoring_time=cfg.get("monitoring_time", "07:00"),
                    engagement_time=cfg.get("engagement_time", "08:00"),
                    content_time=cfg.get("content_time", "09:00"),
                    growth_time=cfg.get("growth_time", "17:00"),
                    timezone=cfg.get("timezone", "UTC"),
                )
            except Exception as e:
                print(f"[scheduler] Could not restore {cfg.get('brand_slug')}: {e}")


# ── Backwards-compat alias (used by existing app.py) ─────────────────────────
DailyScheduler = AgencyScheduler
