"""
Instagram / Meta Graph API wrapper.

In live mode: makes real API calls to Meta Graph API v19.
In demo mode: returns mock responses so the system can run without API credentials.

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


class InstagramAPI:
    BASE_URL = "https://graph.facebook.com/v19.0"

    def __init__(self):
        self.account_id = INSTAGRAM_BUSINESS_ACCOUNT_ID
        self.access_token = META_ACCESS_TOKEN

    # ── Media Publishing ───────────────────────────────────────────────────────

    def create_media_container(
        self,
        media_url: str,
        caption: str,
        media_type: str = "IMAGE",
        is_carousel_item: bool = False,
    ) -> dict:
        """Create a media container (step 1 of 2-step publishing)."""
        if RUN_MODE == "demo" or not self.access_token:
            return {"id": f"mock_container_{int(time.time())}", "status": "demo"}

        endpoint = f"{self.BASE_URL}/{self.account_id}/media"
        payload: dict = {
            "caption": caption,
            "access_token": self.access_token,
        }

        if media_type == "VIDEO" or media_type == "REELS":
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
        if RUN_MODE == "demo" or not self.access_token:
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
        In live mode uses Meta's content_publishing_limit endpoint.
        """
        if RUN_MODE == "demo" or not self.access_token:
            return {
                "status": "demo_scheduled",
                "post_id": post_data.get("post_id"),
                "scheduled_time": post_data.get("scheduled_time"),
                "message": "Would publish via Meta Graph API in live mode",
            }

        try:
            container = self.create_media_container(
                media_url=post_data.get("media_url", ""),
                caption=post_data.get("caption", ""),
                media_type="IMAGE" if post_data.get("post_type") != "reel" else "REELS",
            )
            container_id = container.get("id")
            if not container_id:
                return {"status": "error", "detail": container}

            # Wait for container to be ready
            time.sleep(5)

            result = self.publish_media(container_id)
            result["status"] = "published"
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
        """Fetch account-level insights from Instagram Insights API."""
        if RUN_MODE == "demo" or not self.access_token:
            return self._mock_account_insights(metrics)

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
        """Fetch insights for a specific post."""
        if RUN_MODE == "demo" or not self.access_token:
            return self._mock_post_insights(post_id, metrics)

        endpoint = f"{self.BASE_URL}/{post_id}/insights"
        params = {
            "metric": ",".join(metrics),
            "access_token": self.access_token,
        }
        resp = requests.get(endpoint, params=params, timeout=30)
        return resp.json()

    def get_media_list(self, limit: int = 25) -> dict:
        """Get recent media posts."""
        if RUN_MODE == "demo" or not self.access_token:
            return self._mock_media_list()

        endpoint = f"{self.BASE_URL}/{self.account_id}/media"
        params = {
            "fields": "id,caption,media_type,timestamp,like_count,comments_count",
            "limit": limit,
            "access_token": self.access_token,
        }
        resp = requests.get(endpoint, params=params, timeout=30)
        return resp.json()

    def get_comments(self, media_id: str, limit: int = 50) -> dict:
        """Get comments on a specific post."""
        if RUN_MODE == "demo" or not self.access_token:
            return self._mock_comments()

        endpoint = f"{self.BASE_URL}/{media_id}/comments"
        params = {
            "fields": "id,text,username,timestamp,like_count",
            "limit": limit,
            "access_token": self.access_token,
        }
        resp = requests.get(endpoint, params=params, timeout=30)
        return resp.json()

    def reply_to_comment(self, media_id: str, comment_id: str, reply_text: str) -> dict:
        """Reply to a comment."""
        if RUN_MODE == "demo" or not self.access_token:
            return {"status": "demo_replied", "comment_id": comment_id}

        endpoint = f"{self.BASE_URL}/{media_id}/replies"
        payload = {
            "message": reply_text,
            "access_token": self.access_token,
        }
        resp = requests.post(endpoint, data=payload, timeout=30)
        return resp.json()

    # ── Mock data helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _mock_account_insights(metrics: list) -> dict:
        return {
            "data": [
                {"name": m, "period": "day", "values": [{"value": 100 + i * 50}]}
                for i, m in enumerate(metrics)
            ],
            "source": "demo_mock",
        }

    @staticmethod
    def _mock_post_insights(post_id: str, metrics: list) -> dict:
        mock_values = {
            "impressions": 8400,
            "reach": 5200,
            "likes": 420,
            "comments": 64,
            "shares": 88,
            "saved": 312,
            "engagement": 884,
        }
        return {
            "data": [
                {"name": m, "values": [{"value": mock_values.get(m, 0)}]}
                for m in metrics
            ],
            "source": "demo_mock",
        }

    @staticmethod
    def _mock_media_list() -> dict:
        return {
            "data": [
                {
                    "id": f"post_{i}",
                    "caption": f"Sample post {i} caption #nordicjewellery",
                    "media_type": ["IMAGE", "VIDEO", "CAROUSEL_ALBUM"][i % 3],
                    "timestamp": datetime.now().isoformat(),
                    "like_count": 200 + i * 80,
                    "comments_count": 12 + i * 8,
                }
                for i in range(1, 6)
            ],
            "source": "demo_mock",
        }

    @staticmethod
    def _mock_comments() -> dict:
        return {
            "data": [
                {"id": "c001", "text": "This is beautiful!", "username": "user1", "timestamp": datetime.now().isoformat()},
                {"id": "c002", "text": "How much is this?", "username": "user2", "timestamp": datetime.now().isoformat()},
                {"id": "c003", "text": "Do you ship to the US?", "username": "user3", "timestamp": datetime.now().isoformat()},
            ],
            "source": "demo_mock",
        }
