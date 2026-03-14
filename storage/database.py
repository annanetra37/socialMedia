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
            post_type   TEXT DEFAULT NULL,
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
        # NOTE: idx_bd_posttype is created in the migration block below,
        # after ensuring the post_type column exists.
        """
        CREATE TABLE IF NOT EXISTS product_images (
            brand_slug   TEXT NOT NULL,
            product_idx  INT  NOT NULL,
            image_data   BYTEA NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'image/jpeg',
            public_url   TEXT DEFAULT NULL,
            used         BOOLEAN NOT NULL DEFAULT FALSE,
            used_where   TEXT DEFAULT NULL,
            created_at   TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (brand_slug, product_idx)
        )
        """,
    ]
    with _conn() as conn:
        with conn.cursor() as cur:
            for stmt in stmts:
                cur.execute(stmt)
            # Migrate: add used/used_where columns if table already existed
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='product_images' AND column_name='used'
                    ) THEN
                        ALTER TABLE product_images ADD COLUMN used BOOLEAN NOT NULL DEFAULT FALSE;
                        ALTER TABLE product_images ADD COLUMN used_where TEXT DEFAULT NULL;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='product_images' AND column_name='public_url'
                    ) THEN
                        ALTER TABLE product_images ADD COLUMN public_url TEXT DEFAULT NULL;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='brand_data' AND column_name='post_type'
                    ) THEN
                        ALTER TABLE brand_data ADD COLUMN post_type TEXT DEFAULT NULL;
                        CREATE INDEX IF NOT EXISTS idx_bd_posttype
                            ON brand_data (brand_slug, post_type) WHERE post_type IS NOT NULL;
                    END IF;
                END $$;
            """)
            # Backfill post_type from JSON data for existing rows
            cur.execute("""
                UPDATE brand_data
                SET post_type = data->>'post_type'
                WHERE post_type IS NULL
                  AND data_type IN ('content', 'visuals')
                  AND data->>'post_type' IS NOT NULL
            """)
            # Reels data_type is always post_type='reel'
            cur.execute("""
                UPDATE brand_data
                SET post_type = 'reel'
                WHERE post_type IS NULL AND data_type = 'reels'
            """)
            # Ensure post_type index exists (safe for both fresh and migrated DBs)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_bd_posttype
                    ON brand_data (brand_slug, post_type) WHERE post_type IS NOT NULL
            """)


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


def upsert_data(brand_slug: str, data_type: str, period_key: str, data,
                post_type: str | None = None) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO brand_data (brand_slug, data_type, period_key, post_type, data, updated_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, NOW())
                ON CONFLICT (brand_slug, data_type, period_key) DO UPDATE
                    SET data = EXCLUDED.data, post_type = EXCLUDED.post_type, updated_at = NOW()
                """,
                (brand_slug, data_type, period_key, post_type, _pack(data)),
            )


def get_data(brand_slug: str, data_type: str, period_key: str):
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT data, post_type FROM brand_data WHERE brand_slug=%s AND data_type=%s AND period_key=%s",
                (brand_slug, data_type, period_key),
            )
            row = cur.fetchone()
            if not row:
                return None
            result = _unpack(dict(row["data"]))
            # Inject post_type into the result if it's a dict
            if isinstance(result, dict) and row["post_type"]:
                result.setdefault("post_type", row["post_type"])
            return result


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


def get_all_by_type(brand_slug: str, data_type: str, post_type: str | None = None) -> list[dict]:
    """Return all rows of a given type as a list of dicts.
    Optionally filter by post_type (image, reel, carousel, story)."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if post_type:
                cur.execute(
                    """
                    SELECT period_key, post_type, data FROM brand_data
                    WHERE brand_slug = %s AND data_type = %s AND post_type = %s
                    ORDER BY period_key
                    """,
                    (brand_slug, data_type, post_type),
                )
            else:
                cur.execute(
                    """
                    SELECT period_key, post_type, data FROM brand_data
                    WHERE brand_slug = %s AND data_type = %s
                    ORDER BY period_key
                    """,
                    (brand_slug, data_type),
                )
            return [
                {"period_key": r["period_key"], "post_type": r["post_type"], **_unpack(dict(r["data"]))}
                for r in cur.fetchall()
            ]


# ════════════════════════════════════════════════════════════════════════════
# product_images table
# ════════════════════════════════════════════════════════════════════════════

def upsert_product_image(brand_slug: str, product_idx: int, image_data: bytes,
                         content_type: str, public_url: str | None = None) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO product_images (brand_slug, product_idx, image_data, content_type, public_url)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (brand_slug, product_idx) DO UPDATE
                    SET image_data = EXCLUDED.image_data,
                        content_type = EXCLUDED.content_type,
                        public_url = EXCLUDED.public_url
                """,
                (brand_slug, product_idx, psycopg2.Binary(image_data), content_type, public_url),
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


def get_product_image_public_url(brand_slug: str, product_idx: int) -> str | None:
    """Return the public_url for a product image, if set."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT public_url FROM product_images WHERE brand_slug=%s AND product_idx=%s",
                (brand_slug, product_idx),
            )
            row = cur.fetchone()
            return row[0] if row and row[0] else None


def get_all_product_image_urls(brand_slug: str) -> list[dict]:
    """Return [{product_idx, public_url, used, used_where}] for all images of a brand."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT product_idx, public_url, used, used_where FROM product_images WHERE brand_slug=%s ORDER BY product_idx",
                (brand_slug,),
            )
            return [
                {"product_idx": r[0], "public_url": r[1], "used": r[2], "used_where": r[3]}
                for r in cur.fetchall()
            ]


def mark_image_used(brand_slug: str, product_idx: int, post_id: str) -> None:
    """Mark a product image as used by a specific post/content piece."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE product_images SET used = TRUE, used_where = %s WHERE brand_slug = %s AND product_idx = %s",
                (post_id, brand_slug, product_idx),
            )


def delete_product_image(brand_slug: str, product_idx: int) -> bool:
    """Delete a single product image. Returns True if a row was deleted."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM product_images WHERE brand_slug = %s AND product_idx = %s",
                (brand_slug, product_idx),
            )
            return cur.rowcount > 0


def delete_all_product_images(brand_slug: str) -> int:
    """Delete all product images for a brand. Returns number of rows deleted."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM product_images WHERE brand_slug = %s",
                (brand_slug,),
            )
            return cur.rowcount


def reset_images_used(brand_slug: str) -> None:
    """Reset all images for a brand back to unused (round-robin reset)."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE product_images SET used = FALSE, used_where = NULL WHERE brand_slug = %s",
                (brand_slug,),
            )


def get_available_image_indices(brand_slug: str) -> list[int]:
    """Return product indices that haven't been used yet."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT product_idx FROM product_images WHERE brand_slug = %s AND used = FALSE ORDER BY product_idx",
                (brand_slug,),
            )
            return [row[0] for row in cur.fetchall()]


def get_all_image_indices(brand_slug: str) -> list[int]:
    """Return all product indices for a brand."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT product_idx FROM product_images WHERE brand_slug = %s ORDER BY product_idx",
                (brand_slug,),
            )
            return [row[0] for row in cur.fetchall()]
