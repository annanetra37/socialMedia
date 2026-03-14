"""
PostgreSQL persistence layer.

Tables
------
  brands          — one row per brand (profile stored as JSONB)
  brand_data      — all time-series data keyed by (brand_slug, data_type, period_key)
  product_images  — binary product photos

DATABASE_URL is set automatically by Railway's Postgres plugin.
If DATABASE_URL is not set the app falls back to JSON files (see data_store.py).
"""

import json
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

DATABASE_URL: str = os.getenv("DATABASE_URL", "")


def _url() -> str:
    # Railway provides postgres://, psycopg2 needs postgresql://
    return DATABASE_URL.replace("postgres://", "postgresql://", 1)


@contextmanager
def _conn():
    conn = psycopg2.connect(_url(), connect_timeout=10)
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════════
# Schema
# ════════════════════════════════════════════════════════════════════════════

def init_db() -> None:
    """Create tables and indexes if they don't exist (idempotent)."""
    stmts = [
        """
        CREATE TABLE IF NOT EXISTS brands (
            slug        TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            profile     JSONB NOT NULL,
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            updated_at  TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS brand_data (
            id          BIGSERIAL PRIMARY KEY,
            brand_slug  TEXT NOT NULL,
            data_type   TEXT NOT NULL,
            period_key  TEXT NOT NULL DEFAULT '',
            data        JSONB NOT NULL,
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            updated_at  TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT  brand_data_uq UNIQUE (brand_slug, data_type, period_key),
            CONSTRAINT  brand_data_fk FOREIGN KEY (brand_slug)
                        REFERENCES brands(slug) ON DELETE CASCADE
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_bd_lookup ON brand_data (brand_slug, data_type)",
        "CREATE INDEX IF NOT EXISTS idx_bd_period ON brand_data (brand_slug, data_type, period_key)",
        """
        CREATE TABLE IF NOT EXISTS product_images (
            brand_slug   TEXT NOT NULL,
            product_idx  INT  NOT NULL,
            image_data   BYTEA NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'image/jpeg',
            created_at   TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (brand_slug, product_idx)
        )
        """,
    ]
    with _conn() as conn:
        with conn.cursor() as cur:
            for stmt in stmts:
                cur.execute(stmt)


# ════════════════════════════════════════════════════════════════════════════
# Brands table
# ════════════════════════════════════════════════════════════════════════════

def upsert_brand(slug: str, name: str, profile: dict) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO brands (slug, name, profile, updated_at)
                VALUES (%s, %s, %s::jsonb, NOW())
                ON CONFLICT (slug) DO UPDATE
                    SET name = EXCLUDED.name,
                        profile = EXCLUDED.profile,
                        updated_at = NOW()
                """,
                (slug, name, json.dumps(profile, default=str)),
            )


def get_brand(slug: str) -> dict | None:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT profile FROM brands WHERE slug = %s", (slug,))
            row = cur.fetchone()
            return dict(row["profile"]) if row else None


def list_brands() -> list[dict]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT slug,
                       name,
                       profile->>'industry'         AS industry,
                       profile->>'instagram_handle' AS instagram_handle
                FROM brands
                ORDER BY name
                """
            )
            return [dict(r) for r in cur.fetchall()]


def delete_brand(slug: str) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            # product_images has no FK cascade — delete explicitly
            cur.execute("DELETE FROM product_images WHERE brand_slug = %s", (slug,))
            # brand_data cascades via FK, but delete explicitly to be safe
            cur.execute("DELETE FROM brand_data WHERE brand_slug = %s", (slug,))
            cur.execute("DELETE FROM brands WHERE slug = %s", (slug,))


# ════════════════════════════════════════════════════════════════════════════
# brand_data table  (strategy, trends, campaigns, content, etc.)
# ════════════════════════════════════════════════════════════════════════════

def _pack(data) -> str:
    """Wrap non-dict values so they fit in a JSONB column."""
    if isinstance(data, dict):
        return json.dumps(data, default=str)
    return json.dumps({"_value": data}, default=str)


def _unpack(row_data: dict):
    if row_data and "_value" in row_data and len(row_data) == 1:
        return row_data["_value"]
    return row_data


def upsert_data(brand_slug: str, data_type: str, period_key: str, data) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO brand_data (brand_slug, data_type, period_key, data, updated_at)
                VALUES (%s, %s, %s, %s::jsonb, NOW())
                ON CONFLICT (brand_slug, data_type, period_key) DO UPDATE
                    SET data = EXCLUDED.data, updated_at = NOW()
                """,
                (brand_slug, data_type, period_key, _pack(data)),
            )


def get_data(brand_slug: str, data_type: str, period_key: str):
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT data FROM brand_data WHERE brand_slug=%s AND data_type=%s AND period_key=%s",
                (brand_slug, data_type, period_key),
            )
            row = cur.fetchone()
            return _unpack(dict(row["data"])) if row else None


def get_latest_data(brand_slug: str, data_type: str):
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT data FROM brand_data
                WHERE brand_slug = %s AND data_type = %s
                ORDER BY period_key DESC, updated_at DESC
                LIMIT 1
                """,
                (brand_slug, data_type),
            )
            row = cur.fetchone()
            return _unpack(dict(row["data"])) if row else None


def list_period_keys(brand_slug: str, data_type: str) -> list[str]:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT period_key FROM brand_data WHERE brand_slug=%s AND data_type=%s ORDER BY period_key",
                (brand_slug, data_type),
            )
            return [r[0] for r in cur.fetchall()]


def get_all_by_type(brand_slug: str, data_type: str) -> list[dict]:
    """Return all rows of a given type as a list of dicts."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT period_key, data FROM brand_data
                WHERE brand_slug = %s AND data_type = %s
                ORDER BY period_key
                """,
                (brand_slug, data_type),
            )
            return [{"period_key": r["period_key"], **_unpack(dict(r["data"]))} for r in cur.fetchall()]


# ════════════════════════════════════════════════════════════════════════════
# product_images table
# ════════════════════════════════════════════════════════════════════════════

def upsert_product_image(brand_slug: str, product_idx: int, image_data: bytes, content_type: str) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO product_images (brand_slug, product_idx, image_data, content_type)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (brand_slug, product_idx) DO UPDATE
                    SET image_data = EXCLUDED.image_data, content_type = EXCLUDED.content_type
                """,
                (brand_slug, product_idx, psycopg2.Binary(image_data), content_type),
            )


def get_product_image(brand_slug: str, product_idx: int) -> tuple[bytes, str] | None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT image_data, content_type FROM product_images WHERE brand_slug=%s AND product_idx=%s",
                (brand_slug, product_idx),
            )
            row = cur.fetchone()
            return (bytes(row[0]), row[1]) if row else None
