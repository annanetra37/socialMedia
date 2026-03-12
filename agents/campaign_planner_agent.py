"""
Campaign Planner Agent — The Campaign Director.

Takes the monthly strategy + trend report and produces a detailed
week-by-week, day-by-day posting schedule with post types, themes,
copy briefs and timing recommendations.
"""

import json
from datetime import datetime, timedelta

from .base_agent import AgentTool, BaseAgent
from config.settings import DEFAULT_MODEL, OPTIMAL_POSTING_TIMES, RUN_MODE


class CampaignPlannerAgent(BaseAgent):
    PANEL_COLOR = "bold green"

    def __init__(self, **kwargs):
        super().__init__(
            name="Campaign Planner Agent  [Campaign Director]",
            model=DEFAULT_MODEL,
            use_thinking=False,
            **kwargs,
        )

    def get_system_prompt(self) -> str:
        return """You are an expert social media campaign planner.

Your job is to translate a high-level marketing strategy into a precise,
executable weekly posting calendar.

For each post you define:
- Day and optimal time to post
- Content type (Reel / Carousel / Image / Story)
- Campaign theme it belongs to
- Content brief (what the post should show/say)
- Hook (the first 1-3 seconds / opening line)
- CTA (call to action)
- Hashtag cluster to use
- Priority level (high / medium / low)

You balance:
✓ Content mix targets (reels%, carousels%, etc.)
✓ Optimal posting times per day of week
✓ Spacing posts for maximum reach (not flooding the feed)
✓ Aligning content with the weekly campaign theme
✓ Variety — never two identical post types in a row

Output always ends with structured JSON."""

    def get_tools(self) -> list[AgentTool]:
        return [
            AgentTool(
                name="get_optimal_slots",
                description="Get the best time slots for each day of the week based on audience data.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "platform": {"type": "string", "default": "instagram"},
                        "timezone": {"type": "string", "default": "UTC"},
                    },
                    "required": [],
                },
                executor=self._get_optimal_slots,
            ),
            AgentTool(
                name="calculate_weekly_post_count",
                description="Calculate how many posts of each type to schedule per week.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "posting_frequency": {
                            "type": "object",
                            "description": "From strategy: reels_per_week, carousels_per_week, etc.",
                        },
                    },
                    "required": ["posting_frequency"],
                },
                executor=self._calculate_weekly_post_count,
            ),
        ]

    # ── Main run ───────────────────────────────────────────────────────────────

    def run(self, inputs: dict) -> dict:
        """
        inputs: {
            "brand_profile": dict,
            "strategy_plan": dict,
            "trend_report": dict,
            "week_number": int (1-4)
        }
        returns: campaign_plan dict with posts list
        """
        week = inputs.get("week_number", 1)
        self.print_header(f"Building Week {week} campaign plan")

        brand = inputs["brand_profile"]
        strategy = inputs["strategy_plan"]
        trends = inputs["trend_report"]

        if RUN_MODE == "demo":
            return self._demo_output(brand, strategy, trends, week)

        # Determine current week's theme
        themes = strategy.get("campaign_themes", [])
        current_theme = themes[week - 1] if week <= len(themes) else {"theme": "General"}

        # Posting frequency: prefer strategy output, fall back to brand's stored preference
        posting_freq = strategy.get('posting_frequency') or brand.get('posting_frequency', {
            'reels_per_week': 3, 'carousels_per_week': 2, 'images_per_week': 1, 'stories_per_day': 2
        })
        content_mix = strategy.get('content_mix') or brand.get('content_mix', {})

        prompt = f"""Create a detailed 7-day posting schedule for Week {week}.

BRAND: {brand.get('name')}
WEEK THEME: {json.dumps(current_theme, indent=2)}
STRATEGY (posting frequency & content mix):
{json.dumps(posting_freq, indent=2)}
{json.dumps(content_mix, indent=2)}

TREND INSIGHTS:
{json.dumps(trends.get('viral_formats', [])[:3], indent=2)}
{json.dumps(trends.get('top_recommendations', []), indent=2)}

GROWTH STRATEGY (hooks, CTAs, hashtags):
{json.dumps(strategy.get('growth_strategy', {}), indent=2)}

Please:
1. Use get_optimal_slots to get the best posting times
2. Use calculate_weekly_post_count to determine post type distribution
3. Build the complete 7-day schedule

Output JSON:
```json
{{
  "week_number": {week},
  "theme": "{current_theme.get('theme', '')}",
  "posts": [
    {{
      "id": "post_w{week}_1",
      "day": "Monday",
      "date": "<YYYY-MM-DD>",
      "time": "<HH:MM>",
      "type": "reel|carousel|image|story",
      "priority": "high|medium|low",
      "theme": "<weekly theme>",
      "content_brief": "<what to create>",
      "hook": "<opening hook>",
      "caption_brief": "<tone and key message>",
      "cta": "<call to action>",
      "hashtag_cluster": ["<tag1>", "<tag2>"],
      "visual_notes": "<visual direction>",
      "status": "planned"
    }}
  ],
  "weekly_summary": {{
    "total_posts": <n>,
    "reels": <n>,
    "carousels": <n>,
    "images": <n>,
    "stories": <n>
  }}
}}
```"""

        # Phase 1 — planning conversation (tools + narrative markdown schedule)
        raw = self.call_claude(prompt)

        # Phase 2 — dedicated JSON extraction call
        # Asking Claude to output ONLY the JSON avoids extract_json heuristics entirely.
        json_prompt = (
            "You have just planned the Week " + str(week) + " campaign schedule above. "
            "Now output ONLY the final JSON — no markdown, no explanation, no code fences, "
            "no extra text. Start your response with { and end with }. "
            "The JSON must follow this exact schema:\n"
            '{"week_number": ' + str(week) + ', "theme": "...", "posts": [...], "weekly_summary": {...}}'
        )
        raw_json = self.call_claude(json_prompt, stream_output=False)

        plan = self.extract_json(raw_json)

        # Fallback: try the Phase 1 narrative (may contain a ```json block)
        if not plan.get("posts"):
            plan = self.extract_json(raw) or plan

        # Last resort: store raw so the user can see what happened
        if not plan.get("posts"):
            plan = {"raw_response": raw, "posts": [], "week_number": week}

        self.print_result("Posts scheduled", len(plan.get("posts", [])))
        return plan

    # ── Tool executors ─────────────────────────────────────────────────────────

    @staticmethod
    def _get_optimal_slots(_inputs: dict) -> dict:
        return {"optimal_slots": OPTIMAL_POSTING_TIMES}

    @staticmethod
    def _calculate_weekly_post_count(inputs: dict) -> dict:
        freq = inputs.get("posting_frequency", {})
        return {
            "reels": freq.get("reels_per_week", 3),
            "carousels": freq.get("carousels_per_week", 2),
            "images": freq.get("images_per_week", 1),
            "stories": freq.get("stories_per_day", 2) * 7,
            "total_feed_posts": (
                freq.get("reels_per_week", 3)
                + freq.get("carousels_per_week", 2)
                + freq.get("images_per_week", 1)
            ),
        }

    # ── Demo output ────────────────────────────────────────────────────────────

    @staticmethod
    def _demo_output(brand: dict, strategy: dict, trends: dict, week: int) -> dict:
        themes = strategy.get("campaign_themes", [])
        theme = themes[week - 1] if week <= len(themes) else {"theme": "Brand Showcase"}
        theme_name = theme.get("theme", "Brand Showcase")

        # Build dates for current week
        today = datetime.now()
        # Align to Monday
        monday = today - timedelta(days=today.weekday())
        if week > 1:
            monday += timedelta(weeks=week - 1)

        def day_date(offset: int) -> str:
            return (monday + timedelta(days=offset)).strftime("%Y-%m-%d")

        posts = [
            {
                "id": f"post_w{week}_1",
                "day": "Monday",
                "date": day_date(0),
                "time": "12:00",
                "type": "carousel",
                "priority": "high",
                "theme": theme_name,
                "content_brief": "Educational carousel: 7 meanings behind Norse rune symbols",
                "hook": "\"These symbols were carved by Vikings 1200 years ago…\"",
                "caption_brief": "Educational tone, awe-inspiring, ends with save prompt",
                "cta": "Save this to share with someone who loves Norse culture →",
                "hashtag_cluster": ["#nordicjewellery", "#norsemythology", "#vikingstyle",
                                    "#scandinaviandesign", "#silversmith"],
                "visual_notes": "Flat lay of rune necklace + illustrated rune meanings. Clean white bg.",
                "status": "planned",
            },
            {
                "id": f"post_w{week}_2",
                "day": "Wednesday",
                "date": day_date(2),
                "time": "18:00",
                "type": "reel",
                "priority": "high",
                "theme": theme_name,
                "content_brief": "Process reel: raw silver → finished Norse necklace (ASMR style)",
                "hook": "\"Raw silver to finished necklace in 60 seconds…\"",
                "caption_brief": "Wonder + craftsmanship pride. Short caption, let the video speak.",
                "cta": "Comment MADE if you'd love to own a handmade piece →",
                "hashtag_cluster": ["#handmadejewellery", "#silversmith", "#artisanjewellery",
                                    "#slowcraft", "#nordiccraft"],
                "visual_notes": "Close-up hammer + anvil. Use Wardruna audio. Macro lens on silver.",
                "status": "planned",
            },
            {
                "id": f"post_w{week}_3",
                "day": "Friday",
                "date": day_date(4),
                "time": "13:00",
                "type": "reel",
                "priority": "high",
                "theme": theme_name,
                "content_brief": "Product showcase reel: Norse Rune Necklace worn in natural setting",
                "hook": "\"POV: You just found the perfect gift for someone who loves Norse culture\"",
                "caption_brief": "Aspirational, desire-building. Feature the bestseller.",
                "cta": "DM us RUNE for price and personalisation options →",
                "hashtag_cluster": ["#nordicjewellery", "#giftsforher", "#vikingfashion",
                                    "#handmadegifts", "#ethicaljewellery"],
                "visual_notes": "Model wearing necklace outdoors — forest or stone setting. Golden hour.",
                "status": "planned",
            },
            {
                "id": f"post_w{week}_4",
                "day": "Sunday",
                "date": day_date(6),
                "time": "17:00",
                "type": "image",
                "priority": "medium",
                "theme": theme_name,
                "content_brief": "Community/lifestyle image: flat lay of full collection on marble",
                "hook": "\"Which piece speaks to you? 👇\"",
                "caption_brief": "Community engagement. Ask a question. Warm, inviting tone.",
                "cta": "Comment your favourite below! We read every reply →",
                "hashtag_cluster": ["#nordicjewellery", "#scandinaviandesign", "#jewellerylover",
                                    "#silverjewellery", "#handcrafted"],
                "visual_notes": "Full collection flat lay. White marble. Natural light. Minimal props.",
                "status": "planned",
            },
        ]

        # Add 2 story posts
        posts.extend([
            {
                "id": f"post_w{week}_5",
                "day": "Tuesday",
                "date": day_date(1),
                "time": "09:00",
                "type": "story",
                "priority": "medium",
                "theme": theme_name,
                "content_brief": "Poll story: 'Which Norse symbol resonates with you?'",
                "hook": "Quick question for you 👇",
                "caption_brief": "Interactive, light-hearted",
                "cta": "Vote in our poll →",
                "hashtag_cluster": [],
                "visual_notes": "Branded story template. Two rune options as poll buttons.",
                "status": "planned",
            },
            {
                "id": f"post_w{week}_6",
                "day": "Thursday",
                "date": day_date(3),
                "time": "19:00",
                "type": "story",
                "priority": "medium",
                "theme": theme_name,
                "content_brief": "Behind-the-scenes story: workshop peek, tools on bench",
                "hook": "Thursday in the workshop ✨",
                "caption_brief": "Raw and authentic, swipe up to see process reel",
                "cta": "See the full process reel on our feed →",
                "hashtag_cluster": [],
                "visual_notes": "Candid workshop shot. Tools, silver scraps, workbench.",
                "status": "planned",
            },
        ])

        return {
            "week_number": week,
            "theme": theme_name,
            "brand": brand.get("name", "Brand"),
            "posts": posts,
            "weekly_summary": {
                "total_posts": len(posts),
                "reels": 2,
                "carousels": 1,
                "images": 1,
                "stories": 2,
            },
        }
