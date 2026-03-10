"""
Strategy Agent — The CMO.

Analyses the brand profile, past analytics and competitor landscape to
produce a monthly strategy: content pillars, campaign themes, posting
frequency and growth tactics.

Uses adaptive thinking (Opus 4.6) for deep strategic reasoning.
"""

import json
from datetime import datetime

from .base_agent import AgentTool, BaseAgent
from config.settings import DEFAULT_MODEL, RUN_MODE


class StrategyAgent(BaseAgent):
    PANEL_COLOR = "bold blue"

    def __init__(self, **kwargs):
        super().__init__(
            name="Strategy Agent  [CMO]",
            model=DEFAULT_MODEL,
            use_thinking=True,   # Adaptive thinking for deep strategy
            **kwargs,
        )

    # ── Prompts ────────────────────────────────────────────────────────────────

    def get_system_prompt(self) -> str:
        return """You are a world-class Chief Marketing Officer (CMO) and social media strategist.
Your role is to create data-driven marketing strategies for brands on Instagram.

You think in frameworks:
- Content Pillars (what we talk about and in what ratio)
- Campaign Themes (the emotional story arc for each month/week)
- Growth Levers (hashtags, collaborations, engagement loops, viral hooks)
- Funnel Stages (awareness → engagement → DM → sale)

When analysing a brand, you:
1. Study the audience deeply — their desires, pain points, aspirations
2. Analyse past performance to double down on what works
3. Research competitors to identify white-space opportunities
4. Set SMART goals that are ambitious but realistic
5. Produce a concrete, actionable strategy document

Always output structured JSON at the end of your analysis."""

    def get_tools(self) -> list[AgentTool]:
        return [
            AgentTool(
                name="analyse_competitor",
                description="Fetch basic public metrics and recent post types for a competitor Instagram handle.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "handle": {"type": "string", "description": "Instagram handle (with @)"},
                    },
                    "required": ["handle"],
                },
                executor=self._analyse_competitor,
            ),
            AgentTool(
                name="calculate_content_mix",
                description="Calculate the optimal content type mix based on past performance data.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "past_performance": {
                            "type": "object",
                            "description": "Past performance data from brand profile",
                        },
                        "goals": {
                            "type": "object",
                            "description": "Brand growth goals",
                        },
                    },
                    "required": ["past_performance", "goals"],
                },
                executor=self._calculate_content_mix,
            ),
        ]

    # ── Main run ───────────────────────────────────────────────────────────────

    def run(self, inputs: dict) -> dict:
        """
        inputs: {
            "brand_profile": dict,
            "past_analytics": dict (optional — can be empty),
            "month": str  e.g. "March 2026"
        }
        returns: strategy_plan dict
        """
        self.print_header(f"Generating strategy for {inputs.get('month', 'this month')}")

        brand = inputs["brand_profile"]
        month = inputs.get("month", datetime.now().strftime("%B %Y"))

        prompt = f"""Please create a comprehensive monthly social media strategy for:

BRAND PROFILE:
{json.dumps(brand, indent=2)}

TARGET MONTH: {month}

Tasks to complete:
1. Use the analyse_competitor tool for each competitor listed in the brand profile
2. Use the calculate_content_mix tool with the past_performance and goals data
3. Based on your analysis, produce a complete strategy document

Your output must end with a JSON block in this exact structure:
```json
{{
  "month": "{month}",
  "brand_name": "<brand name>",
  "executive_summary": "<2-3 sentence overview>",
  "content_pillars": [
    {{"name": "<pillar>", "percentage": <0-100>, "rationale": "<why>"}}
  ],
  "campaign_themes": [
    {{"week": 1, "theme": "<theme>", "emotion": "<core emotion>", "hook_style": "<hook>"}}
  ],
  "growth_strategy": {{
    "hashtag_clusters": [["<tag1>", "<tag2>"], ["<tag3>"]],
    "collaboration_angles": ["<idea1>"],
    "viral_hooks": ["<hook1>", "<hook2>"],
    "cta_templates": ["<cta1>", "<cta2>"]
  }},
  "posting_frequency": {{
    "reels_per_week": <n>,
    "carousels_per_week": <n>,
    "images_per_week": <n>,
    "stories_per_day": <n>
  }},
  "kpis": {{
    "followers_target": <n>,
    "engagement_rate_target": <float>,
    "dm_leads_target": <n>
  }},
  "content_mix": {{
    "reels": <float 0-1>,
    "carousels": <float 0-1>,
    "images": <float 0-1>,
    "stories": <float 0-1>
  }}
}}
```"""

        if RUN_MODE == "demo":
            return self._demo_output(brand, month)

        raw = self.call_claude(prompt)
        strategy = self.extract_json(raw)
        if not strategy:
            strategy = {"raw_response": raw}

        self.print_result("Strategy month", strategy.get("month", month))
        self.print_result("Campaigns", len(strategy.get("campaign_themes", [])))
        return strategy

    # ── Tool executors ─────────────────────────────────────────────────────────

    @staticmethod
    def _analyse_competitor(inputs: dict) -> dict:
        handle = inputs.get("handle", "unknown")
        # In live mode this would call Instagram Graph API / scraper
        return {
            "handle": handle,
            "estimated_followers": 35000,
            "avg_likes_per_post": 420,
            "avg_comments_per_post": 18,
            "top_content_types": ["reels", "carousels"],
            "posting_frequency": "5x per week",
            "top_hashtags": ["#handmadejewellery", "#silversmith", "#nordicdesign"],
            "content_themes": ["process videos", "product closeups", "customer stories"],
            "growth_trend": "+2.1% last 30 days",
        }

    @staticmethod
    def _calculate_content_mix(inputs: dict) -> dict:
        perf = inputs.get("past_performance", {})
        goals = inputs.get("goals", {})
        best = perf.get("last_month", {}).get("best_post_type", "reels")

        # Simple heuristic: boost what works best
        mix = {"reels": 0.35, "carousels": 0.30, "images": 0.20, "stories": 0.15}
        if best == "reels":
            mix["reels"] = 0.45
            mix["carousels"] = 0.25
        elif best == "carousels":
            mix["carousels"] = 0.40
            mix["reels"] = 0.30
        return {"recommended_content_mix": mix, "primary_driver": best}

    # ── Demo output (no API call) ──────────────────────────────────────────────

    @staticmethod
    def _demo_output(brand: dict, month: str) -> dict:
        return {
            "month": month,
            "brand_name": brand.get("name", "Brand"),
            "executive_summary": (
                f"Focus {month} on deepening cultural storytelling through reels while "
                "maintaining product visibility. Competitor gap analysis shows an "
                "opportunity in mythological narrative content."
            ),
            "content_pillars": [
                {"name": "Product Showcase", "percentage": 40, "rationale": "Core revenue driver"},
                {"name": "Cultural Storytelling", "percentage": 25, "rationale": "Differentiation + brand trust"},
                {"name": "Lifestyle Inspiration", "percentage": 20, "rationale": "Aspirational pull"},
                {"name": "Craftsmanship Process", "percentage": 15, "rationale": "Trust + educational engagement"},
            ],
            "campaign_themes": [
                {"week": 1, "theme": "Roots of the North", "emotion": "pride", "hook_style": "historical reveal"},
                {"week": 2, "theme": "Made by Hand", "emotion": "trust", "hook_style": "behind-the-scenes"},
                {"week": 3, "theme": "Wear Your Story", "emotion": "identity", "hook_style": "transformation"},
                {"week": 4, "theme": "Spring Equinox Collection", "emotion": "desire", "hook_style": "product launch"},
            ],
            "growth_strategy": {
                "hashtag_clusters": [
                    ["#nordicjewellery", "#scandinaviandesign", "#nordiccraft"],
                    ["#handmadejewellery", "#silversmith", "#artisanjewellery"],
                    ["#vikingstyle", "#norse", "#norsemythology"],
                    ["#sustainablefashion", "#ethicaljewellery", "#slowfashion"],
                ],
                "collaboration_angles": [
                    "Nordic lifestyle micro-influencers (10k–50k followers)",
                    "Sustainable fashion bloggers",
                    "Norse history & culture accounts",
                ],
                "viral_hooks": [
                    "\"This necklace took 14 hours to make. Here's why...\"",
                    "\"Wait until you see the rune pattern appear...\"",
                    "\"POV: You just found your grandmother's Viking ring design\"",
                ],
                "cta_templates": [
                    "Comment RUNE to get the meaning of each symbol →",
                    "Save this if you know someone who'd love this →",
                    "DM us CUSTOM for a personalised design →",
                ],
            },
            "posting_frequency": {
                "reels_per_week": 3,
                "carousels_per_week": 2,
                "images_per_week": 1,
                "stories_per_day": 2,
            },
            "kpis": {
                "followers_target": 500,
                "engagement_rate_target": 5.0,
                "dm_leads_target": 40,
            },
            "content_mix": {
                "reels": 0.45,
                "carousels": 0.30,
                "images": 0.15,
                "stories": 0.10,
            },
        }
