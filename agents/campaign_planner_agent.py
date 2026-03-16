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
- Priority level with intent: "high — boost candidate", "high — organic only", "medium — evergreen", "medium — engagement play", "low — filler", "low — test concept"

You balance:
✓ Content mix targets (reels%, carousels%, etc.)
✓ Optimal posting times per day of week
✓ Spacing posts for maximum reach (not flooding the feed)
✓ Aligning content with the weekly campaign theme
✓ Variety — never two identical post types in a row

Always follow the output format requested by the user message exactly."""

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
            "week_number": int (1-4),
            "target_day": str | None  — e.g. "Monday" to generate for one day only
        }
        returns: campaign_plan dict with posts list
        """
        week = inputs.get("week_number", 1)
        target_day = inputs.get("target_day")
        day_label = f" — {target_day} only" if target_day else ""
        self.print_header(f"Building Week {week}{day_label} campaign plan")

        brand = inputs["brand_profile"]
        strategy = inputs["strategy_plan"]
        trends = inputs["trend_report"]

        if RUN_MODE == "demo":
            plan = self._demo_output(brand, strategy, trends, week)
            if target_day:
                plan["posts"] = [p for p in plan["posts"] if p.get("day", "").lower() == target_day.lower()]
                plan["weekly_summary"] = self._build_summary(plan["posts"])
                plan["target_day"] = target_day
            return plan

        # Determine current week's theme
        themes = strategy.get("campaign_themes", [])
        current_theme = themes[week - 1] if week <= len(themes) else {"theme": "General"}

        # Posting frequency: prefer brand profile (user-configured), fall back to strategy output
        posting_freq = brand.get('posting_frequency') or strategy.get('posting_frequency', {
            'reels_per_week': 3, 'carousels_per_week': 2, 'images_per_week': 1, 'stories_per_day': 2
        })
        content_mix = brand.get('content_mix') or strategy.get('content_mix', {})

        # Build list of disallowed types (0% in content_mix or 0 in posting_frequency)
        disallowed_types = []
        for ctype, mix_key, freq_key in [
            ("carousel", "carousels", "carousels_per_week"),
            ("reel", "reels", "reels_per_week"),
            ("image", "images", "images_per_week"),
            ("story", "stories", "stories_per_day"),
        ]:
            mix_val = content_mix.get(mix_key, None)
            freq_val = posting_freq.get(freq_key, None)
            if mix_val == 0 or freq_val == 0:
                disallowed_types.append(ctype)

        # ── Phase 1: tool calls + JSON-only output ────────────────────────────
        # Claude uses tools to fetch posting times & post-count targets, then
        # outputs the schedule DIRECTLY as a JSON object.  No markdown narrative
        # — this avoids wasting tokens on prose that can't be parsed and
        # prevents hitting the output token limit before the JSON appears.

        # Ensure viral_formats is never empty — provide sensible defaults
        viral_formats = trends.get('viral_formats', [])
        if not viral_formats:
            viral_formats = [
                {"format": "Before → After transformation", "description": "Show a process from start to finish", "best_for": "reels"},
                {"format": "POV storytelling", "description": "First-person narrative perspective", "best_for": "reels"},
                {"format": "Educational carousel", "description": "Teach something valuable in swipeable slides", "best_for": "carousels"},
                {"format": "Behind the scenes", "description": "Raw, authentic look at the process", "best_for": "stories/reels"},
                {"format": "Product showcase", "description": "Highlight product features and benefits", "best_for": "images/carousels"},
                {"format": "User question / poll", "description": "Engage audience with interactive questions", "best_for": "stories"},
            ]

        if target_day:
            schedule_scope = f"a posting schedule for {target_day} of Week {week} (ONE DAY ONLY — do NOT generate posts for other days)"
        else:
            schedule_scope = f"a detailed 7-day posting schedule for Week {week}"

        disallowed_notice = ""
        if disallowed_types:
            disallowed_notice = (
                f"\n\nCRITICAL CONSTRAINT: The brand has DISABLED these post types: {', '.join(disallowed_types)}. "
                f"You must NOT create any posts with type set to: {', '.join(disallowed_types)}. "
                f"Redistribute those slots to the allowed types instead."
            )

        prompt = f"""Create {schedule_scope}.

BRAND: {brand.get('name')}
WEEK THEME: {json.dumps(current_theme, indent=2)}
STRATEGY (posting frequency & content mix):
{json.dumps(posting_freq, indent=2)}
{json.dumps(content_mix, indent=2)}{disallowed_notice}

VIRAL FORMATS FROM TREND RESEARCH (assign one to each post via "trend_format"):
{json.dumps(viral_formats, indent=2)}

TOP RECOMMENDATIONS:
{json.dumps(trends.get('top_recommendations', []), indent=2)}

GROWTH STRATEGY (hooks, CTAs, hashtags):
{json.dumps(strategy.get('growth_strategy', {}), indent=2)}

Steps:
1. Call get_optimal_slots to get the best posting times.
2. Call calculate_weekly_post_count to get the post-type targets.
3. Output the result ONLY as a single ```json``` code block — no markdown tables,
   no commentary before or after, JUST the JSON. Keep content_brief and hook
   values concise (1-2 sentences each).

IMPORTANT: Every post MUST include a "trend_format" field set to the name of the
viral format it uses (from the list above). Match formats to post types
(e.g. "Before → After transformation" for process reels, "POV storytelling" for
narrative reels, etc.). Use the exact format name strings from the trend research.

The JSON must match this exact schema:
```
{{"week_number":{week},"theme":"<week theme>","posts":[
  {{"id":"post_w{week}_1","day":"Monday","date":"YYYY-MM-DD","time":"HH:MM",
    "type":"reel|carousel|image|story","priority":"high — boost candidate|high — organic only|medium — evergreen|medium — engagement play|low — filler|low — test concept",
    "trend_format":"<format name from viral formats above>",
    "theme":"...","content_brief":"...","hook":"...","caption_brief":"...",
    "cta":"...","hashtag_cluster":["tag1","tag2"],"visual_notes":"...","status":"planned"}},
  ...
],"weekly_summary":{{"total_posts":N,"reels":N,"carousels":N,"images":N,"stories":N}}}}
```

IMPORTANT: Output ONLY the JSON object. No markdown summary, no tables, no explanations."""

        raw = self.call_claude(prompt, max_tokens=12000)

        # ── Phase 2: JSON extraction + fallback ─────────────────────────────────
        plan = self.extract_json(raw)

        if not plan.get("posts"):
            # Phase 1 didn't produce parseable JSON with posts.
            # Re-ask with a tight, JSON-only prompt, lower max_tokens to save cost.
            # Truncate the Phase 1 context to the first 4000 chars to avoid
            # wasting input tokens on the full narrative.
            truncated_context = raw[:4000] if len(raw) > 4000 else raw
            json_prompt = (
                "Extract the campaign posts from the schedule above and return "
                "ONLY a JSON object. No markdown, no explanation. "
                f"Start with {{ and end with }}.\n\n"
                "Required schema:\n"
                '{{"week_number":' + str(week) + ',"theme":"...","posts":['
                '{{"id":"post_w' + str(week) + '_1","day":"Monday","date":"YYYY-MM-DD",'
                '"time":"HH:MM","type":"reel|carousel|image|story",'
                '"priority":"high — boost candidate|high — organic only|medium — evergreen|medium — engagement play|low — filler|low — test concept","trend_format":"<viral format name>",'
                '"theme":"...","content_brief":"...",'
                '"hook":"...","caption_brief":"...","cta":"...",'
                '"hashtag_cluster":["tag1"],"visual_notes":"...","status":"planned"}},'
                '...],"weekly_summary":{{"total_posts":N,"reels":N,"carousels":N,"images":N,"stories":N}}}}'
            )
            raw_json = self.call_claude(
                json_prompt,
                extra_context=truncated_context,
                max_tokens=8000,
                stream_output=False,
                use_tools=False,
            )
            plan = self.extract_json(raw_json)

        # Ensure every post has a trend_format — fill from viral_formats if missing
        if plan.get("posts"):
            format_names = [f.get("format", f.get("name", "")) for f in viral_formats]
            type_format_map = {
                "reel": "Before → After transformation",
                "carousel": "Educational carousel",
                "image": "Product showcase",
                "story": "Behind the scenes",
            }
            for p in plan["posts"]:
                if not p.get("trend_format"):
                    post_type = (p.get("type") or "post").lower()
                    p["trend_format"] = type_format_map.get(post_type, format_names[0] if format_names else "General")

        # Enforce disallowed types: convert any disallowed post types to the
        # best allowed alternative (hard constraint — LLM may still slip)
        if disallowed_types and plan.get("posts"):
            allowed = [t for t in ["reel", "image", "carousel", "story"] if t not in disallowed_types]
            fallback = allowed[0] if allowed else "image"
            for p in plan["posts"]:
                if (p.get("type") or "").lower() in disallowed_types:
                    p["type"] = fallback

        # For daily mode: filter to only the target day's posts (safety net
        # in case the LLM still returned multiple days)
        if target_day and plan.get("posts"):
            plan["posts"] = [
                p for p in plan["posts"]
                if p.get("day", "").lower() == target_day.lower()
            ]
            plan["target_day"] = target_day

        # Ensure weekly_summary is always present and consistent with posts
        if plan.get("posts"):
            plan["weekly_summary"] = self._build_summary(plan["posts"])
            plan.setdefault("week_number", week)
        else:
            # Last resort: store raw so the user can see what happened
            plan = {"raw_response": raw, "posts": [], "week_number": week,
                    "weekly_summary": {"total_posts": 0, "reels": 0,
                                       "carousels": 0, "images": 0, "stories": 0}}
            if target_day:
                plan["target_day"] = target_day

        self.print_result("Posts scheduled", len(plan.get("posts", [])))
        return plan

    # ── Helpers ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_summary(posts: list[dict]) -> dict:
        return {
            "total_posts": len(posts),
            "reels": sum(1 for p in posts if p.get("type") == "reel"),
            "carousels": sum(1 for p in posts if p.get("type") == "carousel"),
            "images": sum(1 for p in posts if p.get("type") == "image"),
            "stories": sum(1 for p in posts if p.get("type") == "story"),
        }

    # ── Tool executors ─────────────────────────────────────────────────────────

    @staticmethod
    def _get_optimal_slots(_inputs: dict) -> dict:
        return {"optimal_slots": OPTIMAL_POSTING_TIMES}

    @staticmethod
    def _calculate_weekly_post_count(inputs: dict) -> dict:
        freq = inputs.get("posting_frequency", {})
        reels = freq.get("reels_per_week", 0)
        carousels = freq.get("carousels_per_week", 0)
        images = freq.get("images_per_week", 0)
        stories_per_day = freq.get("stories_per_day", 0)
        result = {
            "reels": reels,
            "carousels": carousels,
            "images": images,
            "stories": stories_per_day * 7,
            "total_feed_posts": reels + carousels + images,
        }
        # Flag types that are explicitly set to 0
        disabled = [t for t, v in [("reels", reels), ("carousels", carousels), ("images", images), ("stories", stories_per_day)] if v == 0]
        if disabled:
            result["disabled_types"] = disabled
            result["note"] = f"Do NOT create posts of these types: {', '.join(disabled)}"
        return result

    # ── Demo output ────────────────────────────────────────────────────────────

    @staticmethod
    def _demo_output(brand: dict, strategy: dict, trends: dict, week: int) -> dict:
        themes = strategy.get("campaign_themes", [])
        theme = themes[week - 1] if week <= len(themes) else {"theme": "Brand Showcase"}
        theme_name = theme.get("theme", "Brand Showcase")
        brand_name = brand.get("name", "Brand")

        # Build dates for current week
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        if week > 1:
            monday += timedelta(weeks=week - 1)

        def day_date(offset: int) -> str:
            return (monday + timedelta(days=offset)).strftime("%Y-%m-%d")

        # ── Respect brand content_mix and posting_frequency ──────────────
        posting_freq = brand.get("posting_frequency") or strategy.get("posting_frequency", {})
        content_mix = brand.get("content_mix") or strategy.get("content_mix", {})

        reels_pw = posting_freq.get("reels_per_week", 3)
        carousels_pw = posting_freq.get("carousels_per_week", 2)
        images_pw = posting_freq.get("images_per_week", 1)
        stories_pd = posting_freq.get("stories_per_day", 2)

        # If content_mix is set and posting_frequency is not, derive counts
        # from mix percentages applied to a reasonable total (e.g. 7 feed posts/week)
        if content_mix and not posting_freq:
            total_feed = 7
            reels_pw = max(0, round(content_mix.get("reels", 0.4) * total_feed))
            carousels_pw = max(0, round(content_mix.get("carousels", 0.3) * total_feed))
            images_pw = max(0, round(content_mix.get("images", 0.2) * total_feed))
            stories_pd = max(0, round(content_mix.get("stories", 0.1) * 3))  # ~3 stories/day at 100%

        # Zero out types that are explicitly 0 in content_mix
        if content_mix.get("reels") == 0: reels_pw = 0
        if content_mix.get("carousels") == 0: carousels_pw = 0
        if content_mix.get("images") == 0: images_pw = 0
        if content_mix.get("stories") == 0: stories_pd = 0

        # Build post slots from counts (stories_per_day → 1 story slot per day capped at stories_pd per week)
        stories_pw = min(stories_pd * 7, 7)  # cap at 7 story posts in the weekly plan
        type_slots = (
            ["reel"] * reels_pw +
            ["carousel"] * carousels_pw +
            ["image"] * images_pw +
            ["story"] * stories_pw
        )

        if not type_slots:
            type_slots = ["image"]  # fallback: at least one post

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        times = ["09:00", "12:00", "13:00", "15:00", "17:00", "18:00", "19:00"]
        priorities = [
            "high — boost candidate", "high — organic only",
            "medium — evergreen", "medium — engagement play",
            "low — filler", "low — test concept",
        ]
        trend_by_type = {
            "reel": "Before → After transformation",
            "carousel": "Educational carousel",
            "image": "Product showcase",
            "story": "Behind the scenes",
        }
        brief_by_type = {
            "reel": (f"Process reel: showcasing {brand_name} in action",
                     f"\"Watch how {brand_name} creates something special…\"",
                     "Wonder + craftsmanship. Short caption, let the video speak.",
                     f"Comment MADE if you love what {brand_name} does →"),
            "carousel": (f"Educational carousel: key insights about {brand_name}",
                         f"\"Did you know? Swipe to discover…\"",
                         "Educational tone, awe-inspiring, ends with save prompt",
                         "Save this and share with a friend →"),
            "image": (f"Lifestyle image: {brand_name} product in context",
                      "\"Which one speaks to you? 👇\"",
                      "Community engagement. Ask a question. Warm tone.",
                      "Comment your favourite below →"),
            "story": (f"Interactive story: quick poll or behind-the-scenes peek",
                      "Quick question for you 👇",
                      "Interactive, light-hearted",
                      "Vote in our poll →"),
        }

        posts = []
        for i, ptype in enumerate(type_slots):
            day_idx = i % 7
            brief, hook, caption, cta = brief_by_type.get(ptype, brief_by_type["image"])
            posts.append({
                "id": f"post_w{week}_{i+1}",
                "day": days[day_idx],
                "date": day_date(day_idx),
                "time": times[i % len(times)],
                "type": ptype,
                "priority": priorities[i % len(priorities)],
                "trend_format": trend_by_type.get(ptype, "Product showcase"),
                "theme": theme_name,
                "content_brief": brief,
                "hook": hook,
                "caption_brief": caption,
                "cta": cta,
                "hashtag_cluster": [f"#{brand_name.lower().replace(' ', '')}"],
                "visual_notes": f"High-quality visual for {ptype} post.",
                "status": "planned",
            })

        summary = CampaignPlannerAgent._build_summary(posts)

        return {
            "week_number": week,
            "theme": theme_name,
            "brand": brand_name,
            "posts": posts,
            "weekly_summary": summary,
        }
