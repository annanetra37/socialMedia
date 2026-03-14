"""
Instagram / Meta Graph API wrapper.

Supports per-brand credentials from the brand profile JSON:
  brand_profile["meta_credentials"] = {
      "access_token": "EAA...",
      "instagram_account_id": "17841...",
  }

Falls back to global .env variables when brand-level credentials are absent.
In demo mode (RUN_MODE=demo) or when no token is set: returns mock data.

Docs: https://developers.facebook.com/docs/instagram-api
"""

import json
import time
from datetime import datetime
from typing import Optional

import requests

from config.settings import (
    INSTAGRAM_BUSINESS_ACCOUNT_ID,
    META_ACCESS_TOKEN,
    RUN_MODE,
)

_PLACEHOLDER_IDS = {
    "",
    "your_instagram_business_account_id_here",
    "CHANGE_ME",
}


class InstagramAPI:
    BASE_URL = "https://graph.facebook.com/v19.0"

    def __init__(self, brand_profile: Optional[dict] = None):
        """
        Priority for credentials:
          1. brand_profile["meta_credentials"]  (per-client credentials)
          2. brand_profile top-level keys       (legacy shorthand)
          3. Global .env vars                   (fallback / single-brand use)
        """
        bp = brand_profile or {}
        creds = bp.get("meta_credentials") or {}

        self.access_token = (
            creds.get("access_token")
            or bp.get("access_token")
            or META_ACCESS_TOKEN
        )
        self.account_id = (
            creds.get("instagram_account_id")
            or creds.get("instagram_business_account_id")
            or bp.get("instagram_account_id")
            or bp.get("instagram_business_account_id")
            or INSTAGRAM_BUSINESS_ACCOUNT_ID
        )

    @property
    def _has_credentials(self) -> bool:
        return bool(
            self.access_token
            and self.account_id
            and self.account_id not in _PLACEHOLDER_IDS
        )

    # ── Media Publishing ───────────────────────────────────────────────────────

    def create_media_container(
        self,
        media_url: str,
        caption: str,
        media_type: str = "IMAGE",
        is_carousel_item: bool = False,
    ) -> dict:
        """Create a media container (step 1 of 2-step publishing)."""
        if RUN_MODE == "demo" or not self._has_credentials:
            return {"id": f"mock_container_{int(time.time())}", "status": "demo"}

        endpoint = f"{self.BASE_URL}/{self.account_id}/media"
        payload: dict = {
            "caption": caption,
            "access_token": self.access_token,
        }

        if media_type in ("VIDEO", "REELS"):
            payload["video_url"] = media_url
            payload["media_type"] = "REELS"
        else:
            payload["image_url"] = media_url
            if is_carousel_item:
                payload["is_carousel_item"] = True

        resp = requests.post(endpoint, data=payload, timeout=60)
        return resp.json()

    def publish_media(self, container_id: str) -> dict:
        """Publish a media container (step 2 of 2-step publishing)."""
        if RUN_MODE == "demo" or not self._has_credentials:
            return {"id": f"mock_post_{int(time.time())}", "status": "demo_published"}

        endpoint = f"{self.BASE_URL}/{self.account_id}/media_publish"
        payload = {
            "creation_id": container_id,
            "access_token": self.access_token,
        }
        resp = requests.post(endpoint, data=payload, timeout=60)
        return resp.json()

    def schedule_post(self, post_data: dict) -> dict:
        """
        Schedule or immediately publish a post.
        Two-step flow: create container → wait → publish.
        """
        if RUN_MODE == "demo" or not self._has_credentials:
            return {
                "status": "demo_scheduled",
                "post_id": post_data.get("post_id"),
                "scheduled_time": post_data.get("scheduled_time"),
                "message": "Would publish via Meta Graph API in live mode",
                "credentials_found": self._has_credentials,
                "account_id_used": self.account_id or "(none)",
            }

        try:
            # STEP 1: Create the media container
            media_url = post_data.get("media_url", "")
            caption = post_data.get("caption", "")
            post_type = (post_data.get("post_type") or "image").lower()
            media_type = "REELS" if post_type == "reel" else "IMAGE"

            container = self.create_media_container(
                media_url=media_url,
                caption=caption,
                media_type=media_type,
            )

            container_id = container.get("id")
            if not container_id:
                err = container.get("error", {})
                msg = err.get("message", "") if isinstance(err, dict) else str(err)
                return {"status": "error", "detail": msg or json.dumps(container)}

            # STEP 2: Wait for Meta to process the media
            time.sleep(5)

            # STEP 3: Publish the container
            result = self.publish_media(container_id)

            if result.get("id"):
                result["status"] = "published"
            else:
                err = result.get("error", {})
                msg = err.get("message", "") if isinstance(err, dict) else str(err)
                result = {"status": "error", "detail": msg or json.dumps(result)}

            return result
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    # ── Account Insights ───────────────────────────────────────────────────────

    def get_account_insights(
        self,
        metrics: list[str],
        period: str = "day",
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> dict:
        if RUN_MODE == "demo" or not self._has_credentials:
            return self._demo_insights(metrics)

        endpoint = f"{self.BASE_URL}/{self.account_id}/insights"
        params: dict = {
            "metric": ",".join(metrics),
            "period": period,
            "access_token": self.access_token,
        }
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        resp = requests.get(endpoint, params=params, timeout=30)
        return resp.json()

    def get_post_insights(self, post_id: str, metrics: list[str]) -> dict:
        if RUN_MODE == "demo" or not self._has_credentials:
            return {"data": [{"name": m, "values": [{"value": 42}]} for m in metrics]}

        endpoint = f"{self.BASE_URL}/{post_id}/insights"
        params = {
            "metric": ",".join(metrics),
            "access_token": self.access_token,
        }
        resp = requests.get(endpoint, params=params, timeout=30)
        return resp.json()

    # ── Media & Comments ───────────────────────────────────────────────────────

    def get_media_list(self, limit: int = 25) -> dict:
        if RUN_MODE == "demo" or not self._has_credentials:
            return {"data": []}

        endpoint = f"{self.BASE_URL}/{self.account_id}/media"
        params = {
            "fields": "id,caption,media_type,timestamp,like_count,comments_count",
            "limit": limit,
            "access_token": self.access_token,
        }
        resp = requests.get(endpoint, params=params, timeout=30)
        return resp.json()

    def get_comments(self, media_id: str, limit: int = 50) -> dict:
        if RUN_MODE == "demo" or not self._has_credentials:
            return {"data": []}

        endpoint = f"{self.BASE_URL}/{media_id}/comments"
        params = {
            "fields": "id,text,username,timestamp",
            "limit": limit,
            "access_token": self.access_token,
        }
        resp = requests.get(endpoint, params=params, timeout=30)
        return resp.json()

    def reply_to_comment(self, comment_id: str, message: str) -> dict:
        if RUN_MODE == "demo" or not self._has_credentials:
            return {"id": f"mock_reply_{int(time.time())}"}

        endpoint = f"{self.BASE_URL}/{comment_id}/replies"
        payload = {
            "message": message,
            "access_token": self.access_token,
        }
        resp = requests.post(endpoint, data=payload, timeout=30)
        return resp.json()

    # ── Demo helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _demo_insights(metrics: list[str]) -> dict:
        from random import randint
        return {
            "data": [
                {
                    "name": m,
                    "period": "day",
                    "values": [{"value": randint(50, 500)}],
                }
                for m in metrics
            ]
        }
