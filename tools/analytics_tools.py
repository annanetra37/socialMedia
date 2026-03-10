"""
Analytics Tools — wrappers around Instagram Insights + computed metrics.
"""

from datetime import datetime, timedelta
from typing import Optional

from config.settings import RUN_MODE
from tools.instagram_api import InstagramAPI


class AnalyticsTools:
    def __init__(self):
        self._api = InstagramAPI()

    def fetch_account_insights(self, inputs: dict) -> dict:
        start = inputs.get("start_date", (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"))
        end = inputs.get("end_date", datetime.now().strftime("%Y-%m-%d"))
        metrics = inputs.get("metrics", ["reach", "impressions", "follower_count", "profile_views"])
        raw = self._api.get_account_insights(metrics=metrics, since=start, until=end)
        return raw

    def fetch_post_metrics(self, inputs: dict) -> dict:
        post_ids = inputs.get("post_ids", [])
        metrics = inputs.get("metrics", ["impressions", "reach", "likes", "comments", "shares", "saved"])
        results = []
        for pid in post_ids:
            data = self._api.get_post_insights(pid, metrics)
            results.append({"post_id": pid, "metrics": data})
        return {"posts": results}

    @staticmethod
    def compute_engagement_rate(
        likes: int,
        comments: int,
        shares: int,
        saves: int,
        follower_count: int,
    ) -> float:
        if not follower_count:
            return 0.0
        total = likes + comments + shares + saves
        return round((total / follower_count) * 100, 2)

    @staticmethod
    def compute_reach_rate(reach: int, follower_count: int) -> float:
        if not follower_count:
            return 0.0
        return round((reach / follower_count) * 100, 2)

    @staticmethod
    def compute_save_rate(saves: int, reach: int) -> float:
        if not reach:
            return 0.0
        return round((saves / reach) * 100, 2)
