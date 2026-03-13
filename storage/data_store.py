"""
DataStore — dual-backend persistence layer.

When DATABASE_URL is set  → all data lives in PostgreSQL (survives redeploys).
Otherwise                 → JSON files under storage/db/<slug>/ (local dev).

The public API is identical in both modes so agents never need to change.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from config.settings import STORAGE_DIR

_USE_DB: bool = bool(os.getenv("DATABASE_URL", ""))

if _USE_DB:
    from storage import database as _db


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


class DataStore:
    def __init__(self, brand_name: str):
        self.brand_slug = _slug(brand_name)
        if not _USE_DB:
            self.root = STORAGE_DIR / self.brand_slug
            self._init_dirs()

    @classmethod
    def from_slug(cls, slug: str) -> "DataStore":
        """Create a DataStore when you already have the slug, not the brand name."""
        obj = cls.__new__(cls)
        obj.brand_slug = slug
        if not _USE_DB:
            obj.root = STORAGE_DIR / slug
            # Don't create directories — only read, this is a read-only path
        return obj

    # ── Filesystem helpers (file backend only) ────────────────────────────────

    def _init_dirs(self) -> None:
        for subdir in [
            "strategy", "trends", "campaigns", "content",
            "visuals", "reels", "engagement", "schedules",
            "analytics", "optimizations",
        ]:
            (self.root / subdir).mkdir(parents=True, exist_ok=True)

    def _fs_save(self, category: str, filename: str, data: Any) -> Path:
        path = self.root / category / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        return path

    def _fs_load(self, category: str, filename: str) -> Optional[Any]:
        if not filename:
            return None
        path = self.root / category / filename
        return json.loads(path.read_text()) if path.exists() else None

    def _fs_list(self, category: str) -> list[str]:
        d = self.root / category
        return sorted(f.name for f in d.glob("*.json")) if d.exists() else []

    def _fs_load_latest(self, category: str) -> Optional[Any]:
        files = self._fs_list(category)
        return self._fs_load(category, files[-1]) if files else None

    # ── Generic save/load (used directly by orchestrator/agents) ─────────────

    def save(self, category: str, filename: str, data: Any) -> Optional[Path]:
        period_key = filename.removesuffix(".json")
        if _USE_DB:
            _db.upsert_data(self.brand_slug, category, period_key, data)
            return None
        return self._fs_save(category, filename, data)

    def load(self, category: str, filename: Optional[str]) -> Optional[Any]:
        if not filename:
            return None
        period_key = filename.removesuffix(".json")
        if _USE_DB:
            return _db.get_data(self.brand_slug, category, period_key)
        return self._fs_load(category, filename)

    def list_files(self, category: str) -> list[str]:
        if _USE_DB:
            return [f"{k}.json" for k in _db.list_period_keys(self.brand_slug, category)]
        return self._fs_list(category)

    def load_latest(self, category: str) -> Optional[Any]:
        if _USE_DB:
            return _db.get_latest_data(self.brand_slug, category)
        return self._fs_load_latest(category)

    def load_all(self, category: str) -> list[Any]:
        """Return data from every file/row in a category."""
        if _USE_DB:
            return [row for row in _db.get_all_by_type(self.brand_slug, category)]
        results = []
        for fname in self._fs_list(category):
            data = self._fs_load(category, fname)
            if data:
                results.append(data)
        return results

    # ── Brand profile ──────────────────────────────────────────────────────────

    def save_brand_profile(self, profile: dict) -> Optional[Path]:
        if _USE_DB:
            _db.upsert_brand(self.brand_slug, profile.get("name", self.brand_slug), profile)
            return None
        path = self.root / "brand_profile.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(profile, ensure_ascii=False, indent=2))
        return path

    def load_brand_profile(self) -> Optional[dict]:
        if _USE_DB:
            return _db.get_brand(self.brand_slug)
        path = self.root / "brand_profile.json"
        return json.loads(path.read_text()) if path.exists() else None

    # ── Typed save/load helpers ────────────────────────────────────────────────

    def save_strategy(self, strategy: dict, month: Optional[str] = None) -> Optional[Path]:
        month = month or datetime.now().strftime("%Y-%m")
        return self.save("strategy", f"{month}.json", strategy)

    def load_strategy(self, month: Optional[str] = None) -> Optional[dict]:
        month = month or datetime.now().strftime("%Y-%m")
        return self.load("strategy", f"{month}.json")

    def save_trend_report(self, report: dict, date: Optional[str] = None) -> Optional[Path]:
        date = date or datetime.now().strftime("%Y-%m-%d")
        return self.save("trends", f"{date}.json", report)

    def load_trend_report(self, date: Optional[str] = None) -> Optional[dict]:
        date = date or datetime.now().strftime("%Y-%m-%d")
        result = self.load("trends", f"{date}.json")
        return result if result else self.load_latest("trends")

    def save_campaign(self, campaign: dict, month: Optional[str] = None, week: int = 1) -> Optional[Path]:
        month = month or datetime.now().strftime("%Y-%m")
        return self.save("campaigns", f"{month}_w{week:02d}.json", campaign)

    def load_campaign(self, month: Optional[str] = None, week: int = 1) -> Optional[dict]:
        month = month or datetime.now().strftime("%Y-%m")
        return self.load("campaigns", f"{month}_w{week:02d}.json")

    def save_content(self, content: dict, post_id: str) -> Optional[Path]:
        return self.save("content", f"{post_id}.json", content)

    def load_content(self, post_id: str) -> Optional[dict]:
        return self.load("content", f"{post_id}.json")

    def save_visual(self, visual: dict, post_id: str) -> Optional[Path]:
        return self.save("visuals", f"{post_id}.json", visual)

    def load_visual(self, post_id: str) -> Optional[dict]:
        return self.load("visuals", f"{post_id}.json")

    def save_reel(self, reel: dict, post_id: str) -> Optional[Path]:
        return self.save("reels", f"{post_id}.json", reel)

    def save_engagement(self, responses: dict, date: Optional[str] = None) -> Optional[Path]:
        date = date or datetime.now().strftime("%Y-%m-%d")
        return self.save("engagement", f"{date}.json", responses)

    def save_schedule(self, schedule: dict, month: Optional[str] = None, week: int = 1) -> Optional[Path]:
        month = month or datetime.now().strftime("%Y-%m")
        return self.save("schedules", f"{month}_w{week:02d}.json", schedule)

    def save_analytics(self, report: dict, period: str = "weekly", date: Optional[str] = None) -> Optional[Path]:
        date = date or datetime.now().strftime("%Y-%m-%d")
        return self.save("analytics", f"{date}_{period}.json", report)

    def load_latest_analytics(self) -> Optional[dict]:
        return self.load_latest("analytics")

    def save_optimization(self, recommendations: dict, date: Optional[str] = None) -> Optional[Path]:
        date = date or datetime.now().strftime("%Y-%m-%d")
        return self.save("optimizations", f"{date}.json", recommendations)

    def load_latest_optimization(self) -> Optional[dict]:
        return self.load_latest("optimizations")

    # ── Used product image tracking ───────────────────────────────────────────

    def load_used_images(self) -> list[dict]:
        """Return list of {product_idx, post_id} records for images already used."""
        data = self.load("used_images", "tracker.json")
        if isinstance(data, dict):
            return data.get("used", [])
        return []

    def save_used_image(self, product_idx: int, post_id: str) -> None:
        """Mark a product image as used by a specific post."""
        records = self.load_used_images()
        records.append({"product_idx": product_idx, "post_id": post_id})
        self.save("used_images", "tracker.json", {"used": records})

    def get_available_product_indices(self, brand: dict) -> list[int]:
        """Return product indices that haven't been used yet.
        If all are used, reset and return all (round-robin)."""
        products = brand.get("products", [])
        if not products:
            return []
        all_indices = list(range(len(products)))
        used = self.load_used_images()
        used_indices = {r["product_idx"] for r in used}
        available = [i for i in all_indices if i not in used_indices]
        if not available:
            # All photos used — reset tracker and return all
            self.save("used_images", "tracker.json", {"used": []})
            available = all_indices
        return available

    # ── Summary ────────────────────────────────────────────────────────────────

    def get_session_summary(self) -> dict:
        return {
            "brand": self.brand_slug,
            "strategy_files":     self.list_files("strategy"),
            "trend_files":        self.list_files("trends"),
            "campaign_files":     self.list_files("campaigns"),
            "content_files":      self.list_files("content"),
            "analytics_files":    self.list_files("analytics"),
            "optimization_files": self.list_files("optimizations"),
            "last_updated":       datetime.now().isoformat(),
        }
