"""
Optimization Agent — The Growth Hacker.

Closes the feedback loop. Takes analytics data and past campaign
performance to produce concrete strategy improvements that feed
back into the next Strategy Agent cycle.

Uses adaptive thinking for deep analysis.
"""

import json
from datetime import datetime

from .base_agent import AgentTool, BaseAgent
from config.settings import DEFAULT_MODEL, RUN_MODE


class OptimizationAgent(BaseAgent):
    PANEL_COLOR = "bold red"

    def __init__(self, **kwargs):
        super().__init__(
            name="Optimization Agent  [Growth Hacker]",
            model=DEFAULT_MODEL,
            use_thinking=True,  # Deep thinking for strategy improvements
            **kwargs,
        )

    def get_system_prompt(self) -> str:
        return """You are a growth-hacking optimization specialist who analyses social media
performance data to extract learnings and generate concrete improvements.

Your optimization framework:
1. DIAGNOSE: What happened vs what was expected?
2. EXPLAIN: Root-cause analysis (why did it happen?)
3. PRESCRIBE: Specific actions to improve (not vague advice — concrete changes)
4. PREDICT: What will the new approach achieve?

You think in experiments:
- What's the hypothesis?
- What will we change?
- How will we measure success?
- What's the expected lift?

Your recommendations are always:
- Specific (not "post better content" but "increase reel frequency to 4/week and use transformation format")
- Measurable (attach KPI targets)
- Actionable (can be implemented next week)
- Prioritised (quick wins vs long-term plays)

You identify the 20% of changes that will drive 80% of the improvement."""

    def get_tools(self) -> list[AgentTool]:
        return [
            AgentTool(
                name="compare_performance_vs_benchmark",
                description="Compare current performance against industry benchmarks and past results.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "current_metrics": {"type": "object"},
                        "past_metrics": {"type": "object"},
                        "industry": {"type": "string"},
                    },
                    "required": ["current_metrics"],
                },
                executor=self._compare_vs_benchmark,
            ),
            AgentTool(
                name="identify_growth_levers",
                description="Identify the top growth levers based on performance data.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "analytics_data": {"type": "object"},
                        "current_strategy": {"type": "object"},
                    },
                    "required": ["analytics_data"],
                },
                executor=self._identify_growth_levers,
            ),
            AgentTool(
                name="generate_ab_test_ideas",
                description="Generate A/B test ideas for underperforming content types.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "underperforming_area": {"type": "string"},
                        "current_approach": {"type": "string"},
                    },
                    "required": ["underperforming_area"],
                },
                executor=self._generate_ab_tests,
            ),
        ]

    # ── Main run ───────────────────────────────────────────────────────────────

    def run(self, inputs: dict) -> dict:
        """
        inputs: {
            "brand_profile": dict,
            "analytics_report": dict,
            "strategy_plan": dict,
            "campaign_plan": dict
        }
        returns: optimization_recommendations dict (feeds back to Strategy Agent)
        """
        brand = inputs["brand_profile"]
        analytics = inputs["analytics_report"]
        strategy = inputs.get("strategy_plan", {})

        self.print_header(f"Generating optimizations for {brand.get('name')}")

        if RUN_MODE == "demo":
            return self._demo_output(brand, analytics, strategy)

        prompt = f"""Analyse this week's performance data and generate specific improvements
for the next campaign cycle.

BRAND: {brand.get('name')}
ANALYTICS REPORT:
{json.dumps(analytics, indent=2)}

CURRENT STRATEGY:
{json.dumps(strategy, indent=2)}

Please:
1. Use compare_performance_vs_benchmark to evaluate performance
2. Use identify_growth_levers to find the highest-impact improvements
3. Use generate_ab_test_ideas for the worst-performing content type

Output JSON with ALL the specific improvements to feed back into next week's strategy:
```json
{{
  "optimization_date": "{datetime.now().isoformat()[:10]}",
  "brand": "{brand.get('name')}",
  "performance_verdict": "excellent|good|average|poor",
  "key_learnings": [
    {{
      "observation": "<what happened>",
      "root_cause": "<why it happened>",
      "action": "<what to do differently>"
    }}
  ],
  "content_mix_update": {{
    "current": {{}},
    "recommended": {{}},
    "reasoning": "<why this change>"
  }},
  "quick_wins": [
    {{
      "action": "<specific action>",
      "expected_impact": "<measurable outcome>",
      "effort": "low|medium|high",
      "timeline": "next_post|this_week|next_month"
    }}
  ],
  "strategic_shifts": [
    {{
      "shift": "<what to change strategically>",
      "from": "<current approach>",
      "to": "<new approach>",
      "hypothesis": "<why this will work>",
      "success_metric": "<how to measure>"
    }}
  ],
  "ab_tests_to_run": [
    {{
      "test_name": "<name>",
      "variable": "<what we're testing>",
      "control": "<current>",
      "variant": "<new version>",
      "success_criterion": "<measure>",
      "duration": "<how long>"
    }}
  ],
  "next_week_priorities": [
    "<priority 1>",
    "<priority 2>",
    "<priority 3>"
  ],
  "updated_kpis": {{
    "followers_weekly_target": <n>,
    "engagement_rate_target": <float>,
    "reels_per_week": <n>
  }}
}}
```"""

        raw = self.call_claude(prompt)
        optimizations = self.extract_json(raw)
        if not optimizations:
            optimizations = {"raw_response": raw}

        wins = len(optimizations.get("quick_wins", []))
        self.print_result("Quick wins identified", wins)
        return optimizations

    # ── Tool executors ─────────────────────────────────────────────────────────

    @staticmethod
    def _compare_vs_benchmark(inputs: dict) -> dict:
        metrics = inputs.get("current_metrics", {})
        industry = inputs.get("industry", "jewellery")
        benchmarks = {
            "jewellery": {
                "avg_engagement_rate": 3.5,
                "avg_follower_growth_monthly": 2.5,
                "avg_reach_rate": 12.0,
            }
        }
        bench = benchmarks.get(industry, benchmarks["jewellery"])
        curr_eng = metrics.get("avg_engagement_rate", 0)
        return {
            "industry": industry,
            "benchmarks": bench,
            "your_engagement_vs_benchmark": f"{curr_eng} vs {bench['avg_engagement_rate']} industry avg",
            "status": "above" if curr_eng > bench["avg_engagement_rate"] else "below",
            "gap": round(curr_eng - bench["avg_engagement_rate"], 2),
        }

    @staticmethod
    def _identify_growth_levers(inputs: dict) -> dict:
        data = inputs.get("analytics_data", {})
        content_breakdown = data.get("content_type_breakdown", {})
        reels_eng = content_breakdown.get("reels", {}).get("avg_engagement", 0)
        images_eng = content_breakdown.get("images", {}).get("avg_engagement", 0)
        levers = []
        if reels_eng > images_eng * 1.5:
            levers.append({"lever": "Increase reel frequency", "impact": "high", "data": f"Reels {reels_eng}% vs images {images_eng}%"})
        dm_funnel = data.get("dm_funnel", {})
        if dm_funnel.get("leads_qualified", 0) > dm_funnel.get("sales_from_social", 0) * 2:
            levers.append({"lever": "Improve DM-to-sale conversion", "impact": "high", "data": "Lead qualification too high vs close rate"})
        return {"growth_levers": levers}

    @staticmethod
    def _generate_ab_tests(inputs: dict) -> dict:
        area = inputs.get("underperforming_area", "images")
        tests = {
            "images": [
                {"test": "Hook text overlay vs no text", "hypothesis": "Text overlay will stop scroll and increase reach by 20%"},
                {"test": "Product only vs product in lifestyle setting", "hypothesis": "Lifestyle context will increase saves by 40%"},
            ],
            "captions": [
                {"test": "Short (50 words) vs long (200 words) caption", "hypothesis": "Long captions drive more comments and saves"},
                {"test": "Question CTA vs action CTA", "hypothesis": "Question CTA drives 30% more comments"},
            ],
            "reels": [
                {"test": "POV format vs transformation format", "hypothesis": "POV format will improve watch-through rate"},
                {"test": "With voiceover vs music only", "hypothesis": "Voiceover increases education signals and saves"},
            ],
        }
        return {"ab_tests": tests.get(area, tests["images"])}

    # ── Demo output ────────────────────────────────────────────────────────────

    @staticmethod
    def _demo_output(brand: dict, analytics: dict, strategy: dict) -> dict:
        current_mix = strategy.get("content_mix", {"reels": 0.40, "carousels": 0.30, "images": 0.20, "stories": 0.10})
        content_bd = analytics.get("content_type_breakdown", {})
        reel_eng = content_bd.get("reels", {}).get("avg_engagement", 7.75)
        img_eng = content_bd.get("images", {}).get("avg_engagement", 2.9)

        return {
            "optimization_date": datetime.now().isoformat()[:10],
            "brand": brand.get("name", "Brand"),
            "performance_verdict": "good",
            "key_learnings": [
                {
                    "observation": f"Reels achieving {reel_eng}% engagement vs images at {img_eng}%",
                    "root_cause": f"Reels benefit from algorithmic distribution AND are preferred by target audience. Images lack motion + hook capability.",
                    "action": "Shift content mix: Increase reels to 50%, reduce images to 10%",
                },
                {
                    "observation": "Educational carousel (rune meanings) had highest saves (890) of the week",
                    "root_cause": "Audience finds cultural/educational content highly valuable and bookmark-worthy — save rate indicates they want to return to it.",
                    "action": "Create 1 'save-worthy' educational carousel per week as a permanent fixture",
                },
                {
                    "observation": "Follower growth (214) behind target (500) but engagement exceeded target (6.1% vs 5.0%)",
                    "root_cause": "Content is resonating deeply with existing audience but not reaching enough new people. Reach amplification needed.",
                    "action": "Add 2-3 collaborative posts or hashtag-led reach campaigns next week",
                },
            ],
            "content_mix_update": {
                "current": current_mix,
                "recommended": {
                    "reels": 0.50,
                    "carousels": 0.30,
                    "images": 0.10,
                    "stories": 0.10,
                },
                "reasoning": f"Reels are driving {round(reel_eng / img_eng, 1)}x more engagement than images. Reallocating 10% from images to reels will drive significantly more reach.",
            },
            "quick_wins": [
                {
                    "action": "Post a 'Nordic Symbol' educational carousel every Monday",
                    "expected_impact": "Consistent save-heavy post type → 40% increase in weekly saves",
                    "effort": "medium",
                    "timeline": "this_week",
                },
                {
                    "action": "Add 'Save this to share' as the closing CTA on all educational posts",
                    "expected_impact": "+25% saves per post (directly signals content value to algorithm)",
                    "effort": "low",
                    "timeline": "next_post",
                },
                {
                    "action": "Reply to ALL comments within 2 hours of posting (use engagement windows)",
                    "expected_impact": "2-hour reply window boosts algorithmic reach by ~15-20%",
                    "effort": "low",
                    "timeline": "next_post",
                },
                {
                    "action": "Use Wardruna / Sigur Rós audio on all reels for 2 weeks",
                    "expected_impact": "Trending Norse audio gives 30-40% algorithmic boost + aligns with brand identity",
                    "effort": "low",
                    "timeline": "this_week",
                },
            ],
            "strategic_shifts": [
                {
                    "shift": "Increase reel production cadence",
                    "from": "3 reels/week",
                    "to": "4 reels/week (add one 'micro-reel' under 15 seconds)",
                    "hypothesis": "Micro-reels (15s) have higher completion rates and generate more reach per post",
                    "success_metric": "Track reach per reel — target 8000+ per reel within 3 weeks",
                },
                {
                    "shift": "Add hashtag-led reach strategy",
                    "from": "Brand hashtags only",
                    "to": "Mix of brand + trending + community hashtags per post",
                    "hypothesis": "Trending hashtags will add 500-1500 reach per post from hashtag discovery",
                    "success_metric": "Hashtag-driven reach > 15% of total post reach",
                },
            ],
            "ab_tests_to_run": [
                {
                    "test_name": "Reel Hook Format Test",
                    "variable": "Opening frame type",
                    "control": "Text hook first (3 words)",
                    "variant": "Visual hook first (no text in first 2s)",
                    "success_criterion": "3-second view rate > 70%",
                    "duration": "2 weeks / 4 reels",
                },
                {
                    "test_name": "Caption CTA Test",
                    "variable": "CTA style",
                    "control": "Comment CTA (Comment CRAFT)",
                    "variant": "Save CTA (Save this for [reason])",
                    "success_criterion": "Save rate > 4% of reach",
                    "duration": "2 weeks / 4 posts",
                },
            ],
            "next_week_priorities": [
                "Produce 4 reels (1 process, 1 POV story, 1 product reveal, 1 micro-reel 15s)",
                "Create 'Norse Rune Week 2' educational carousel for Monday",
                "Implement Wardruna audio strategy on all reels",
                "Process all hot leads from this week (3 identified) — close the DM conversations",
            ],
            "updated_kpis": {
                "followers_weekly_target": 300,  # More realistic based on data
                "engagement_rate_target": 6.5,   # Raise the bar — we exceeded 5%
                "reels_per_week": 4,             # Increase from 3
            },
        }
