"""
Analytics Agent — The Data Analyst.

Pulls performance data from Instagram Insights, processes it into
actionable metrics and surfaces the key learnings from each campaign.
"""

import json
from datetime import datetime

from .base_agent import AgentTool, BaseAgent
from config.settings import DEFAULT_MODEL, RUN_MODE
from tools.analytics_tools import AnalyticsTools


class AnalyticsAgent(BaseAgent):
    PANEL_COLOR = "bold magenta"

    def __init__(self, **kwargs):
        super().__init__(
            name="Analytics Agent  [Data Analyst]",
            model=DEFAULT_MODEL,
            use_thinking=False,
            **kwargs,
        )
        self._analytics = AnalyticsTools()

    def get_system_prompt(self) -> str:
        return """You are a data-driven social media analyst who turns raw metrics into
actionable insights for content creators and marketers.

You analyse:
- Follower growth (net new, growth rate, churn)
- Engagement metrics (rate, likes, comments, shares, saves)
- Reach and impressions (organic vs paid, reach rate)
- Content performance (by type, theme, time)
- Story performance (tap-forward rate, exit rate, swipe-up)
- DM conversion (comments/reach → DM enquiries → sales)
- Hashtag performance (which drove real reach)

You identify:
- Top-performing content patterns (not just best posts — WHY they worked)
- Underperforming content (and root cause)
- Growth opportunities (what to double down on)
- Audience behaviour patterns (when they engage, what they save)
- Conversion funnel leaks (where potential buyers drop off)

You always frame metrics as stories, not just numbers:
"Reels drove 68% of new followers this month — 3.4x the rate of carousels"
Not: "Reels: 420 followers, Carousels: 124 followers."

Output structured JSON with both the data and the narrative."""

    def get_tools(self) -> list[AgentTool]:
        return [
            AgentTool(
                name="fetch_instagram_insights",
                description="Fetch Instagram account-level insights for a date range.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                        "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                        "metrics": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "e.g. ['reach', 'impressions', 'follower_count']",
                        },
                    },
                    "required": ["start_date", "end_date"],
                },
                executor=self._fetch_insights,
            ),
            AgentTool(
                name="fetch_post_performance",
                description="Fetch performance metrics for specific posts.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "post_ids": {"type": "array", "items": {"type": "string"}},
                        "metrics": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["post_ids"],
                },
                executor=self._fetch_post_performance,
            ),
            AgentTool(
                name="calculate_engagement_rate",
                description="Calculate engagement rate for a set of posts.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "posts_data": {"type": "array"},
                        "follower_count": {"type": "integer"},
                    },
                    "required": ["posts_data", "follower_count"],
                },
                executor=self._calculate_engagement_rate,
            ),
        ]

    # ── Main run ───────────────────────────────────────────────────────────────

    def run(self, inputs: dict) -> dict:
        """
        inputs: {
            "brand_profile": dict,
            "campaign_plan": dict,
            "published_posts": list[dict],
            "period": "weekly" | "monthly"
        }
        returns: analytics_report dict
        """
        brand = inputs["brand_profile"]
        period = inputs.get("period", "weekly")
        published = inputs.get("published_posts", [])

        self.print_header(f"Analysing {period} performance for {brand.get('name')}")

        if RUN_MODE == "demo":
            return self._demo_output(brand, period, published)

        prompt = f"""Analyse the {period} social media performance for {brand.get('name')}.

BRAND: {brand.get('name')}
CURRENT FOLLOWERS: {brand.get('social_media', {}).get('instagram', {}).get('current_followers', 'unknown')}
KPIS:
{json.dumps(inputs.get('campaign_plan', {}).get('kpis', {}), indent=2)}

Please:
1. Use fetch_instagram_insights for the past 7 days (if weekly) or 30 days
2. Use fetch_post_performance for all published posts
3. Use calculate_engagement_rate to compute the overall rate

Output JSON:
```json
{{
  "report_period": "{period}",
  "generated_at": "{datetime.now().isoformat()}",
  "account_metrics": {{
    "followers_start": <n>,
    "followers_end": <n>,
    "followers_gained": <n>,
    "follower_growth_rate": "<x%>",
    "total_reach": <n>,
    "total_impressions": <n>,
    "profile_visits": <n>,
    "website_clicks": <n>
  }},
  "content_performance": {{
    "total_posts": <n>,
    "avg_engagement_rate": <float>,
    "avg_likes": <n>,
    "avg_comments": <n>,
    "avg_shares": <n>,
    "avg_saves": <n>,
    "best_post": {{
      "id": "<id>",
      "type": "<type>",
      "engagement_rate": <float>,
      "why_it_worked": "<analysis>"
    }},
    "worst_post": {{
      "id": "<id>",
      "type": "<type>",
      "engagement_rate": <float>,
      "why_it_underperformed": "<analysis>"
    }}
  }},
  "content_type_breakdown": {{
    "reels": {{"posts": <n>, "avg_engagement": <float>, "avg_reach": <n>}},
    "carousels": {{"posts": <n>, "avg_engagement": <float>, "avg_reach": <n>}},
    "images": {{"posts": <n>, "avg_engagement": <float>, "avg_reach": <n>}},
    "stories": {{"posts": <n>, "avg_views": <n>, "avg_exit_rate": "<x%>"}}
  }},
  "dm_funnel": {{
    "new_dms": <n>,
    "leads_qualified": <n>,
    "sales_from_social": <n>,
    "conversion_rate": "<x%>"
  }},
  "hashtag_performance": [
    {{"hashtag": "<tag>", "reach_from_hashtag": <n>, "verdict": "keep|test|drop"}}
  ],
  "key_insights": [
    "<insight 1>",
    "<insight 2>",
    "<insight 3>"
  ],
  "kpi_scorecard": {{
    "followers_target": <n>,
    "followers_achieved": <n>,
    "followers_status": "on_track|behind|exceeded",
    "engagement_target": <float>,
    "engagement_achieved": <float>,
    "engagement_status": "on_track|behind|exceeded"
  }}
}}
```"""

        raw = self.call_claude(prompt)
        report = self.extract_json(raw)
        if not report:
            report = {"raw_response": raw}

        gained = report.get("account_metrics", {}).get("followers_gained", 0)
        self.print_result("Followers gained", gained)
        return report

    # ── Tool executors ─────────────────────────────────────────────────────────

    def _fetch_insights(self, inputs: dict) -> dict:
        if RUN_MODE == "live":
            return self._analytics.fetch_account_insights(inputs)
        return {
            "follower_count_start": 8420,
            "follower_count_end": 8634,
            "total_reach": 42800,
            "total_impressions": 87600,
            "profile_visits": 1840,
            "website_clicks": 124,
            "period": f"{inputs.get('start_date')} to {inputs.get('end_date')}",
        }

    def _fetch_post_performance(self, inputs: dict) -> dict:
        if RUN_MODE == "live":
            return self._analytics.fetch_post_metrics(inputs)
        return {
            "posts": [
                {"id": "p001", "type": "reel", "reach": 8420, "impressions": 12400, "likes": 684, "comments": 92, "shares": 156, "saves": 420, "engagement_rate": 8.1},
                {"id": "p002", "type": "carousel", "reach": 4200, "impressions": 6800, "likes": 310, "comments": 68, "shares": 45, "saves": 890, "engagement_rate": 6.2},
                {"id": "p003", "type": "image", "reach": 2100, "impressions": 3400, "likes": 148, "comments": 12, "shares": 8, "saves": 56, "engagement_rate": 2.9},
                {"id": "p004", "type": "reel", "reach": 6800, "impressions": 11200, "likes": 520, "comments": 74, "shares": 110, "saves": 380, "engagement_rate": 7.4},
            ]
        }

    @staticmethod
    def _calculate_engagement_rate(inputs: dict) -> dict:
        posts = inputs.get("posts_data", [])
        followers = inputs.get("follower_count", 1)
        if not posts:
            return {"avg_engagement_rate": 0}
        rates = []
        for post in posts:
            total_eng = post.get("likes", 0) + post.get("comments", 0) + post.get("shares", 0) + post.get("saves", 0)
            rate = (total_eng / followers) * 100 if followers else 0
            rates.append(rate)
        return {
            "avg_engagement_rate": round(sum(rates) / len(rates), 2),
            "by_post": rates,
        }

    # ── Demo output ────────────────────────────────────────────────────────────

    @staticmethod
    def _demo_output(brand: dict, period: str, published: list) -> dict:
        followers = brand.get("social_media", {}).get("instagram", {}).get("current_followers", 8420)
        return {
            "report_period": period,
            "generated_at": datetime.now().isoformat(),
            "account_metrics": {
                "followers_start": followers,
                "followers_end": followers + 214,
                "followers_gained": 214,
                "follower_growth_rate": f"+{round(214/followers*100, 1)}%",
                "total_reach": 42800,
                "total_impressions": 87600,
                "profile_visits": 1840,
                "website_clicks": 124,
            },
            "content_performance": {
                "total_posts": 4,
                "avg_engagement_rate": 6.1,
                "avg_likes": 415,
                "avg_comments": 61,
                "avg_shares": 80,
                "avg_saves": 436,
                "best_post": {
                    "id": "post_w1_2",
                    "type": "reel",
                    "engagement_rate": 8.1,
                    "why_it_worked": "Process transformation content + trending Norse audio. Hook in first 3s caused strong watch-through rate (72%). High share velocity spread to new audiences.",
                },
                "worst_post": {
                    "id": "post_w1_4",
                    "type": "image",
                    "engagement_rate": 2.9,
                    "why_it_underperformed": "Static product image without storytelling or hook. Competed in a crowded feed. No save incentive in caption.",
                },
            },
            "content_type_breakdown": {
                "reels": {"posts": 2, "avg_engagement": 7.75, "avg_reach": 7610},
                "carousels": {"posts": 1, "avg_engagement": 6.2, "avg_reach": 4200},
                "images": {"posts": 1, "avg_engagement": 2.9, "avg_reach": 2100},
                "stories": {"posts": 2, "avg_views": 1240, "avg_exit_rate": "18%"},
            },
            "dm_funnel": {
                "new_dms": 28,
                "leads_qualified": 9,
                "sales_from_social": 5,
                "conversion_rate": "17.9%",
            },
            "hashtag_performance": [
                {"hashtag": "#nordicjewellery", "reach_from_hashtag": 1840, "verdict": "keep"},
                {"hashtag": "#silversmith", "reach_from_hashtag": 1240, "verdict": "keep"},
                {"hashtag": "#handmadejewellery", "reach_from_hashtag": 680, "verdict": "keep"},
                {"hashtag": "#vikingfashion", "reach_from_hashtag": 920, "verdict": "keep"},
                {"hashtag": "#jewellery", "reach_from_hashtag": 84, "verdict": "drop"},
            ],
            "key_insights": [
                "Reels drove 3.8x more reach than images — strongly outperforming all other formats",
                "Educational carousel (rune meanings) has highest saves count (890) — bookmarked for future reference",
                "Posts at 18:00 got 42% more reach than 12:00 posts — audience most active in evening",
                "Norse cultural content outperformed product-only content by 2.1x engagement",
            ],
            "kpi_scorecard": {
                "followers_target": 500,
                "followers_achieved": 214,
                "followers_status": "behind",
                "engagement_target": 5.0,
                "engagement_achieved": 6.1,
                "engagement_status": "exceeded",
            },
        }
