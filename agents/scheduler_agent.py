"""
Scheduler Agent — The Publisher.

Takes approved posts and schedules / publishes them via the
Meta Graph API (Instagram). In demo mode, generates the schedule
without calling real APIs.
"""

import json
from datetime import datetime

from .base_agent import AgentTool, BaseAgent
from config.settings import DEFAULT_MODEL, META_ACCESS_TOKEN, RUN_MODE
from tools.instagram_api import InstagramAPI


class SchedulerAgent(BaseAgent):
    PANEL_COLOR = "bold white"

    def __init__(self, **kwargs):
        super().__init__(
            name="Scheduler Agent  [Publisher]",
            model=DEFAULT_MODEL,
            use_thinking=False,
            **kwargs,
        )
        self._ig_api = InstagramAPI()

    def get_system_prompt(self) -> str:
        return """You are a social media publishing specialist who optimises posting schedules
for maximum algorithmic reach and audience engagement.

You understand:
- Instagram's algorithm rewards consistent, timely posting
- Each post type has different optimal windows
- Spacing matters — never post twice within 3 hours on the feed
- Stories can be posted more frequently (2-4/day)
- Time zones of the target audience determine actual UTC publish times

When scheduling posts you:
1. Validate that all required content is present (caption, media, hashtags)
2. Check for scheduling conflicts (too close together)
3. Assign final UTC timestamps
4. Queue posts in the correct order
5. Generate a publishing manifest (summary of what publishes when)"""

    def get_tools(self) -> list[AgentTool]:
        return [
            AgentTool(
                name="validate_post_ready",
                description="Validate that a post has all required fields before scheduling.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "post": {"type": "object", "description": "The full post package"},
                    },
                    "required": ["post"],
                },
                executor=self._validate_post_ready,
            ),
            AgentTool(
                name="schedule_instagram_post",
                description="Schedule or publish a post via the Meta Graph API.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "post_id": {"type": "string"},
                        "caption": {"type": "string"},
                        "media_url": {"type": "string"},
                        "post_type": {"type": "string", "enum": ["image", "carousel", "reel", "story"]},
                        "scheduled_time": {"type": "string", "description": "ISO 8601 UTC datetime"},
                    },
                    "required": ["post_id", "caption", "media_url", "post_type"],
                },
                executor=self._schedule_instagram_post,
            ),
            AgentTool(
                name="check_best_time_to_post",
                description="Calculate the optimal posting time for a specific content type and audience.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "post_type": {"type": "string"},
                        "day_of_week": {"type": "string"},
                        "audience_timezone": {"type": "string", "default": "Europe/London"},
                    },
                    "required": ["post_type", "day_of_week"],
                },
                executor=self._check_best_time,
            ),
        ]

    # ── Main run ───────────────────────────────────────────────────────────────

    def run(self, inputs: dict) -> dict:
        """
        inputs: {
            "campaign_plan": dict (with posts list),
            "content_packages": list[dict],
            "brand_profile": dict
        }
        returns: publishing_manifest dict
        """
        brand = inputs["brand_profile"]
        campaign = inputs.get("campaign_plan", {})
        posts = campaign.get("posts", [])
        content_packages = inputs.get("content_packages", [])

        self.print_header(f"Scheduling {len(posts)} posts for {brand.get('name')}")

        if RUN_MODE == "demo":
            return self._demo_output(brand, posts, content_packages)

        # Build a map of content packages by post_id
        content_map = {cp.get("post_id"): cp for cp in content_packages}

        prompt = f"""Schedule and validate all posts for this week's campaign.

BRAND: {brand.get('name')}
CAMPAIGN PLAN: {json.dumps(campaign, indent=2)}
CONTENT PACKAGES: {json.dumps(content_packages[:3], indent=2)} (and {max(0, len(content_packages)-3)} more)

Please:
1. Use check_best_time_to_post for each post to confirm optimal timing
2. Use validate_post_ready for each post
3. Use schedule_instagram_post for each valid post

Output JSON:
```json
{{
  "schedule_created_at": "{datetime.now().isoformat()}",
  "brand": "{brand.get('name')}",
  "week_number": {campaign.get('week_number', 1)},
  "scheduled_posts": [
    {{
      "post_id": "<id>",
      "day": "<day>",
      "scheduled_datetime_utc": "<ISO datetime>",
      "post_type": "<type>",
      "caption_preview": "<first 100 chars>",
      "status": "scheduled|published|failed",
      "platform_post_id": "<meta post id or null>",
      "notes": "<any notes>"
    }}
  ],
  "publishing_manifest": {{
    "total_posts": <n>,
    "this_week_feed_posts": <n>,
    "this_week_stories": <n>,
    "first_post": "<datetime>",
    "last_post": "<datetime>"
  }},
  "warnings": ["<any scheduling issues>"]
}}
```"""

        raw = self.call_claude(prompt)
        manifest = self.extract_json(raw)
        if not manifest:
            manifest = {"raw_response": raw}

        scheduled = len(manifest.get("scheduled_posts", []))
        self.print_result("Posts scheduled", scheduled)
        return manifest

    # ── Tool executors ─────────────────────────────────────────────────────────

    @staticmethod
    def _validate_post_ready(inputs: dict) -> dict:
        post = inputs.get("post", {})
        issues = []
        if not post.get("caption") and not post.get("content_brief"):
            issues.append("Missing caption")
        if not post.get("time"):
            issues.append("Missing scheduled time")
        return {
            "post_id": post.get("id", "unknown"),
            "valid": len(issues) == 0,
            "issues": issues,
        }

    def _schedule_instagram_post(self, inputs: dict) -> dict:
        if not META_ACCESS_TOKEN:
            return {
                "status": "demo_mode",
                "post_id": inputs.get("post_id"),
                "message": "Meta API token not configured — would publish in live mode",
                "scheduled_time": inputs.get("scheduled_time"),
            }
        return self._ig_api.schedule_post(inputs)

    @staticmethod
    def _check_best_time(inputs: dict) -> dict:
        day = inputs.get("day_of_week", "Monday").lower()
        post_type = inputs.get("post_type", "image")
        from config.settings import OPTIMAL_POSTING_TIMES
        times = OPTIMAL_POSTING_TIMES.get(day, ["12:00", "18:00"])
        # Reels perform best in the evening slot
        if post_type == "reel":
            return {"optimal_time": times[-1], "reasoning": "Reels peak in evening slot (higher engagement)"}
        return {"optimal_time": times[0], "reasoning": "Carousels/images peak at lunch"}

    # ── Demo output ────────────────────────────────────────────────────────────

    @staticmethod
    def _demo_output(brand: dict, posts: list, content_packages: list) -> dict:
        content_map = {cp.get("post_id"): cp for cp in content_packages}
        scheduled = []
        for post in posts:
            pid = post.get("id")
            cp = content_map.get(pid, {})
            caption = cp.get("caption", {}).get("full_caption", post.get("content_brief", ""))
            scheduled.append({
                "post_id": pid,
                "day": post.get("day"),
                "scheduled_datetime_utc": f"{post.get('date', '2026-03-10')}T{post.get('time', '12:00')}:00Z",
                "post_type": post.get("type"),
                "caption_preview": (caption[:100] + "...") if len(caption) > 100 else caption,
                "status": "scheduled",
                "platform_post_id": None,
                "notes": "Demo mode — will publish via Meta Graph API in live mode",
            })

        feed_posts = [p for p in scheduled if p["post_type"] != "story"]
        stories = [p for p in scheduled if p["post_type"] == "story"]
        first = scheduled[0]["scheduled_datetime_utc"] if scheduled else None
        last = scheduled[-1]["scheduled_datetime_utc"] if scheduled else None

        return {
            "schedule_created_at": datetime.now().isoformat(),
            "brand": brand.get("name", "Brand"),
            "week_number": 1,
            "scheduled_posts": scheduled,
            "publishing_manifest": {
                "total_posts": len(scheduled),
                "this_week_feed_posts": len(feed_posts),
                "this_week_stories": len(stories),
                "first_post": first,
                "last_post": last,
            },
            "warnings": [],
        }
