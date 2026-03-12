"""
Global application settings loaded from environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage" / "db"
BRAND_PROFILES_DIR = BASE_DIR / "config" / "brand_profiles"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# ── Anthropic ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DEFAULT_MODEL = "claude-opus-4-6"           # Opus 4.6 — most capable
FAST_MODEL = "claude-haiku-4-5"             # Haiku 4.5 — for quick tasks

# ── Meta / Instagram ──────────────────────────────────────────────────────────
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")           # legacy fallback; prefer OAuth
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")  # legacy fallback
META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")

# ── Image Generation ──────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY", "")

# ── Trend Data ────────────────────────────────────────────────────────────────
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")  # set automatically by Railway Postgres plugin

# ── App behaviour ─────────────────────────────────────────────────────────────
RUN_MODE = os.getenv("RUN_MODE", "demo")     # "demo" | "live"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
TIMEZONE = os.getenv("TIMEZONE", "UTC")

# ── Daily cycle block times (24-h HH:MM) ─────────────────────────────────────
MONITORING_TIME = "07:00"
ENGAGEMENT_TIME = "08:00"
CONTENT_TIME = "09:00"
GROWTH_TIME = "17:00"
ANALYTICS_TIME = "22:00"

# ── Content mix targets ───────────────────────────────────────────────────────
DEFAULT_CONTENT_MIX = {
    "reels": 0.40,
    "carousels": 0.30,
    "images": 0.20,
    "stories": 0.10,
}

# ── Optimal posting windows ───────────────────────────────────────────────────
OPTIMAL_POSTING_TIMES = {
    "monday":    ["12:00", "18:00"],
    "tuesday":   ["11:00", "17:00"],
    "wednesday": ["12:00", "18:00"],
    "thursday":  ["11:00", "17:00"],
    "friday":    ["13:00", "19:00"],
    "saturday":  ["10:00", "16:00"],
    "sunday":    ["11:00", "17:00"],
}
