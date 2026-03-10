"""
Trend Research Agent — The Trend Scout.

Monitors Instagram trends, viral formats, hashtag performance and
competitor activity to surface timely content opportunities.
"""

import json
from datetime import datetime

from .base_agent import AgentTool, BaseAgent
from config.settings import DEFAULT_MODEL, RUN_MODE


class TrendResearchAgent(BaseAgent):
    PANEL_COLOR = "bold magenta"

    def __init__(self, **kwargs):
        super().__init__(
            name="Trend Research Agent  [Trend Scout]",
            model=DEFAULT_MODEL,
            use_thinking=False,
            **kwargs,
        )

    def get_system_prompt(self) -> str:
        return """You are an expert social media trend analyst who monitors Instagram,
TikTok, and digital culture in real time.

Your specialities:
- Identifying viral content formats BEFORE they peak (early mover advantage)
- Spotting trending audio/music for Reels
- Hashtag performance analysis (which are rising, which are saturated)
- Competitor content monitoring — what's working for them right now
- Cross-platform trend migration (TikTok → Instagram Reels timeline)

When researching trends for a brand you:
1. Use all available tools to gather fresh data
2. Filter trends through the brand's voice and audience lens
3. Rate each trend for fit (1–10) and urgency (immediate / this week / this month)
4. Suggest specific hooks, audio and formats to leverage each trend

Always output structured JSON at the end of your report."""

    def get_tools(self) -> list[AgentTool]:
        return [
            AgentTool(
                name="fetch_trending_hashtags",
                description="Fetch currently trending hashtags in a given niche/industry.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "niche": {"type": "string", "description": "Industry or topic niche"},
                        "limit": {"type": "integer", "description": "Max hashtags to return", "default": 20},
                    },
                    "required": ["niche"],
                },
                executor=self._fetch_trending_hashtags,
            ),
            AgentTool(
                name="fetch_viral_reel_formats",
                description="Fetch currently viral Reel formats and hooks in a niche.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "niche": {"type": "string"},
                        "platform": {
                            "type": "string",
                            "enum": ["instagram", "tiktok", "both"],
                            "default": "both",
                        },
                    },
                    "required": ["niche"],
                },
                executor=self._fetch_viral_reel_formats,
            ),
            AgentTool(
                name="fetch_competitor_recent_posts",
                description="Retrieve the most recent posts and their engagement from a competitor.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "handle": {"type": "string"},
                        "days_back": {"type": "integer", "default": 7},
                    },
                    "required": ["handle"],
                },
                executor=self._fetch_competitor_recent_posts,
            ),
            AgentTool(
                name="fetch_trending_audio",
                description="Fetch trending audio tracks suitable for Reels in a given mood/genre.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "mood": {
                            "type": "string",
                            "description": "e.g. 'elegant', 'energetic', 'nostalgic'",
                        },
                    },
                    "required": ["mood"],
                },
                executor=self._fetch_trending_audio,
            ),
        ]

    # ── Main run ───────────────────────────────────────────────────────────────

    def run(self, inputs: dict) -> dict:
        """
        inputs: {
            "brand_profile": dict,
            "strategy_plan": dict
        }
        returns: trend_report dict
        """
        self.print_header("Scanning trends")

        brand = inputs["brand_profile"]
        industry = brand.get("industry", "jewellery")

        if RUN_MODE == "demo":
            return self._demo_output(brand)

        prompt = f"""Research current social media trends for this brand and strategy.

BRAND: {brand.get('name')} — {industry}
AUDIENCE: {json.dumps(brand.get('target_audience', {}), indent=2)}
BRAND VOICE: {brand.get('brand_voice', '')}

Please:
1. Use fetch_trending_hashtags for the brand's niche
2. Use fetch_viral_reel_formats for the brand's niche
3. Use fetch_competitor_recent_posts for each competitor
4. Use fetch_trending_audio for the brand's mood/aesthetic

Then synthesise your findings into a trend report with actionable content recommendations.

Output a JSON block with this structure:
```json
{{
  "report_date": "{datetime.now().isoformat()[:10]}",
  "trending_topics": [
    {{
      "topic": "<topic>",
      "platform": "<platform>",
      "fit_score": <1-10>,
      "urgency": "immediate|this_week|this_month",
      "content_angle": "<how to use for brand>",
      "hook_example": "<example hook>"
    }}
  ],
  "trending_hashtags": {{
    "primary": ["<tag>"],
    "secondary": ["<tag>"],
    "niche": ["<tag>"]
  }},
  "viral_formats": [
    {{
      "format": "<format name>",
      "description": "<description>",
      "example_hook": "<hook>",
      "best_for": "<content pillar it supports>"
    }}
  ],
  "trending_audio": [
    {{"track": "<name>", "mood": "<mood>", "uses_count": "<approx>"}}
  ],
  "competitor_insights": [
    {{
      "handle": "<handle>",
      "best_performing_post_type": "<type>",
      "key_observation": "<insight>",
      "opportunity": "<gap we can exploit>"
    }}
  ],
  "top_recommendations": [
    "<actionable recommendation 1>",
    "<actionable recommendation 2>",
    "<actionable recommendation 3>"
  ]
}}
```"""

        raw = self.call_claude(prompt)
        trend_report = self.extract_json(raw)
        if not trend_report:
            trend_report = {"raw_response": raw}

        self.print_result("Trending topics found", len(trend_report.get("trending_topics", [])))
        return trend_report

    # ── Tool executors ─────────────────────────────────────────────────────────

    @staticmethod
    def _fetch_trending_hashtags(inputs: dict) -> dict:
        niche = inputs.get("niche", "jewellery")
        return {
            "niche": niche,
            "trending": [
                {"tag": "#nordicjewellery", "posts": "180K", "growth": "+12%"},
                {"tag": "#handmadejewellery", "posts": "4.2M", "growth": "+3%"},
                {"tag": "#silversmith", "posts": "920K", "growth": "+8%"},
                {"tag": "#artisanjewellery", "posts": "1.1M", "growth": "+5%"},
                {"tag": "#vikingfashion", "posts": "340K", "growth": "+22%"},
                {"tag": "#norsestyle", "posts": "210K", "growth": "+18%"},
                {"tag": "#scandinaviandesign", "posts": "2.8M", "growth": "+4%"},
                {"tag": "#slowjewellery", "posts": "90K", "growth": "+35%"},
                {"tag": "#ethicaljewellery", "posts": "280K", "growth": "+15%"},
                {"tag": "#giftsforher", "posts": "8.9M", "growth": "+2%"},
            ],
            "saturated_avoid": ["#jewellery", "#fashion", "#style"],
        }

    @staticmethod
    def _fetch_viral_reel_formats(inputs: dict) -> dict:
        return {
            "formats": [
                {
                    "name": "Before → After transformation",
                    "description": "Raw material to finished piece",
                    "avg_views_multiplier": 2.8,
                    "hook": "\"Raw silver to finished necklace in 60 seconds\"",
                },
                {
                    "name": "POV storytelling",
                    "description": "First-person narrative about the piece's meaning",
                    "avg_views_multiplier": 3.2,
                    "hook": "\"POV: You inherited your grandmother's Viking ring\"",
                },
                {
                    "name": "Historical reveal",
                    "description": "Educational reveal about cultural significance",
                    "avg_views_multiplier": 2.5,
                    "hook": "\"This symbol protected Viking warriors for 1000 years\"",
                },
                {
                    "name": "ASMR crafting",
                    "description": "Close-up sensory crafting sounds",
                    "avg_views_multiplier": 2.1,
                    "hook": "\"The sound of silver being shaped...\"",
                },
                {
                    "name": "Trend duet / stitch response",
                    "description": "React to trending culture through your product lens",
                    "avg_views_multiplier": 4.0,
                    "hook": "\"Bridgerton inspired our new collection and here's why\"",
                },
            ]
        }

    @staticmethod
    def _fetch_competitor_recent_posts(inputs: dict) -> dict:
        handle = inputs.get("handle", "@competitor")
        return {
            "handle": handle,
            "top_posts_last_7_days": [
                {
                    "type": "reel",
                    "description": "Crafting process — hammer and anvil",
                    "likes": 1840,
                    "comments": 92,
                    "shares": 234,
                    "saves": 680,
                },
                {
                    "type": "carousel",
                    "description": "7 meanings behind Norse rune symbols",
                    "likes": 1220,
                    "comments": 156,
                    "shares": 89,
                    "saves": 1100,
                },
                {
                    "type": "image",
                    "description": "Product flat lay — white marble",
                    "likes": 480,
                    "comments": 22,
                    "shares": 12,
                    "saves": 95,
                },
            ],
            "insight": "Reels and educational carousels massively outperform static images",
        }

    @staticmethod
    def _fetch_trending_audio(inputs: dict) -> dict:
        mood = inputs.get("mood", "elegant")
        return {
            "mood": mood,
            "trending_tracks": [
                {"track": "Hoppípolla — Sigur Rós", "uses": "2.1M", "vibe": "epic, emotional"},
                {"track": "River Flows in You — Yiruma", "uses": "890K", "vibe": "delicate, artisan"},
                {"track": "Nordland — Wardruna", "uses": "340K", "vibe": "Norse, cultural"},
                {"track": "Experience — Ludovico Einaudi", "uses": "1.4M", "vibe": "luxury, aspirational"},
            ],
        }

    # ── Demo output ────────────────────────────────────────────────────────────

    @staticmethod
    def _demo_output(brand: dict) -> dict:
        return {
            "report_date": datetime.now().isoformat()[:10],
            "trending_topics": [
                {
                    "topic": "Viking / Norse revival",
                    "platform": "Instagram + TikTok",
                    "fit_score": 10,
                    "urgency": "immediate",
                    "content_angle": "Show how our pieces connect to authentic Norse heritage",
                    "hook_example": "\"This rune symbol protected Vikings 1200 years ago...\"",
                },
                {
                    "topic": "Slow craftsmanship movement",
                    "platform": "Instagram",
                    "fit_score": 9,
                    "urgency": "this_week",
                    "content_angle": "Behind-the-scenes artisan process — hammer, anvil, fire",
                    "hook_example": "\"Every piece takes 14+ hours. Here's the process...\"",
                },
                {
                    "topic": "Sustainable luxury",
                    "platform": "both",
                    "fit_score": 8,
                    "urgency": "this_month",
                    "content_angle": "Ethical sourcing story — silver origin and environmental care",
                    "hook_example": "\"Our silver is 100% recycled. Here's where it comes from\"",
                },
            ],
            "trending_hashtags": {
                "primary": ["#nordicjewellery", "#silversmith", "#handmadejewellery"],
                "secondary": ["#vikingfashion", "#norsestyle", "#artisanjewellery"],
                "niche": ["#slowjewellery", "#ethicaljewellery", "#scandinaviancraft"],
            },
            "viral_formats": [
                {
                    "format": "Before → After transformation",
                    "description": "Raw silver to finished necklace timelapse",
                    "example_hook": "\"Raw silver to Norse rune necklace in 60 seconds\"",
                    "best_for": "Craftsmanship Process pillar",
                },
                {
                    "format": "POV storytelling",
                    "description": "First-person narrative tied to cultural moment",
                    "example_hook": "\"POV: You discover your great-grandmother was a silversmith\"",
                    "best_for": "Cultural Storytelling pillar",
                },
                {
                    "format": "Historical symbol reveal",
                    "description": "Reveal the hidden meaning behind a design element",
                    "example_hook": "\"This symbol was carved on Viking longships for 800 years\"",
                    "best_for": "Cultural Storytelling pillar",
                },
            ],
            "trending_audio": [
                {"track": "Hoppípolla — Sigur Rós", "mood": "epic/emotional", "uses_count": "2.1M"},
                {"track": "Nordland — Wardruna", "mood": "Norse/cultural", "uses_count": "340K"},
            ],
            "competitor_insights": [
                {
                    "handle": "@nordiccraft_jewels",
                    "best_performing_post_type": "process reels",
                    "key_observation": "Crafting ASMR reels getting 3x their normal reach",
                    "opportunity": "Educational cultural carousels — they don't do this",
                },
            ],
            "top_recommendations": [
                "Launch a 3-part 'Norse Symbol Meaning' carousel series this week",
                "Film a hammer-and-anvil crafting ASMR reel using Wardruna audio",
                "Use '#slowjewellery' cluster — low competition, high growth (+35%)",
            ],
        }
