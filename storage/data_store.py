"""
DataStore — simple JSON-file-based persistence layer.

Directory layout:
  storage/db/
    <brand_slug>/
      brand_profile.json
      strategy/
        YYYY-MM.json          ← monthly strategy
      trends/
        YYYY-MM-DD.json       ← daily trend report
      campaigns/
        YYYY-MM_wNN.json      ← weekly campaign plan
      content/
        <post_id>.json        ← full content package per post
      visuals/
        <post_id>.json
      reels/
        <post_id>.json
      engagement/
        YYYY-MM-DD.json
      schedules/
        YYYY-MM_wNN.json
      analytics/
        YYYY-MM-DD.json
        YYYY-MM.json
      optimizations/
        YYYY-MM-DD.json
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from config.settings import STORAGE_DIR


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


class DataStore:
    def __init__(self, brand_name: str):
        self.brand_slug = _slug(brand_name)
        self.root = STORAGE_DIR / self.brand_slug
        self._init_dirs()

    def _init_dirs(self) -> None:
        for subdir in [
            "strategy", "trends", "campaigns", "content",
            "visuals", "reels", "engagement", "schedules",
            "analytics", "optimizations",
        ]:
            (self.root / subdir).mkdir(parents=True, exist_ok=True)

    # ── Generic read/write ─────────────────────────────────────────────────────

    def save(self, category: str, filename: str, data: Any) -> Path:
        """Save any dict/list to a JSON file."""
        path = self.root / category / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return path

    def load(self, category: str, filename: str) -> Optional[Any]:
        """Load a JSON file. Returns None if not found."""
        path = self.root / category / filename
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def list_files(self, category: str) -> list[str]:
        """List all JSON file names in a category directory."""
        directory = self.root / category
        return sorted(f.name for f in directory.glob("*.json"))

    def load_latest(self, category: str) -> Optional[Any]:
        """Load the most recently modified file in a category."""
        files = self.list_files(category)
        if not files:
            return None
        return self.load(category, files[-1])

    # ── Typed helpers ──────────────────────────────────────────────────────────

    def save_brand_profile(self, profile: dict) -> Path:
        return self.save(".", "brand_profile.json", profile)

    def load_brand_profile(self) -> Optional[dict]:
        path = self.root / "brand_profile.json"
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save_strategy(self, strategy: dict, month: Optional[str] = None) -> Path:
        month = month or datetime.now().strftime("%Y-%m")
        return self.save("strategy", f"{month}.json", strategy)

    def load_strategy(self, month: Optional[str] = None) -> Optional[dict]:
        month = month or datetime.now().strftime("%Y-%m")
        return self.load("strategy", f"{month}.json")

    def save_trend_report(self, report: dict, date: Optional[str] = None) -> Path:
        date = date or datetime.now().strftime("%Y-%m-%d")
        return self.save("trends", f"{date}.json", report)

    def load_trend_report(self, date: Optional[str] = None) -> Optional[dict]:
        date = date or datetime.now().strftime("%Y-%m-%d")
        result = self.load("trends", f"{date}.json")
        if not result:
            result = self.load_latest("trends")
        return result

    def save_campaign(self, campaign: dict, month: Optional[str] = None, week: int = 1) -> Path:
        month = month or datetime.now().strftime("%Y-%m")
        return self.save("campaigns", f"{month}_w{week:02d}.json", campaign)

    def load_campaign(self, month: Optional[str] = None, week: int = 1) -> Optional[dict]:
        month = month or datetime.now().strftime("%Y-%m")
        return self.load("campaigns", f"{month}_w{week:02d}.json")

    def save_content(self, content: dict, post_id: str) -> Path:
        return self.save("content", f"{post_id}.json", content)

    def load_content(self, post_id: str) -> Optional[dict]:
        return self.load("content", f"{post_id}.json")

    def save_visual(self, visual: dict, post_id: str) -> Path:
        return self.save("visuals", f"{post_id}.json", visual)

    def load_visual(self, post_id: str) -> Optional[dict]:
        return self.load("visuals", f"{post_id}.json")

    def save_reel(self, reel: dict, post_id: str) -> Path:
        return self.save("reels", f"{post_id}.json", reel)

    def save_engagement(self, responses: dict, date: Optional[str] = None) -> Path:
        date = date or datetime.now().strftime("%Y-%m-%d")
        return self.save("engagement", f"{date}.json", responses)

    def save_schedule(self, schedule: dict, month: Optional[str] = None, week: int = 1) -> Path:
        month = month or datetime.now().strftime("%Y-%m")
        return self.save("schedules", f"{month}_w{week:02d}.json", schedule)

    def save_analytics(self, report: dict, period: str = "weekly", date: Optional[str] = None) -> Path:
        date = date or datetime.now().strftime("%Y-%m-%d")
        filename = f"{date}_{period}.json"
        return self.save("analytics", filename, report)

    def load_latest_analytics(self) -> Optional[dict]:
        return self.load_latest("analytics")

    def save_optimization(self, recommendations: dict, date: Optional[str] = None) -> Path:
        date = date or datetime.now().strftime("%Y-%m-%d")
        return self.save("optimizations", f"{date}.json", recommendations)

    def load_latest_optimization(self) -> Optional[dict]:
        return self.load_latest("optimizations")

    # ── Summary helpers ────────────────────────────────────────────────────────

    def get_session_summary(self) -> dict:
        """Return a high-level summary of stored data for this brand."""
        return {
            "brand": self.brand_slug,
            "strategy_files": self.list_files("strategy"),
            "trend_files": self.list_files("trends"),
            "campaign_files": self.list_files("campaigns"),
            "content_files": self.list_files("content"),
            "analytics_files": self.list_files("analytics"),
            "optimization_files": self.list_files("optimizations"),
            "last_updated": datetime.now().isoformat(),
        }
