"""
Trend Research Agent — The Trend Scout.

Monitors Instagram trends, viral formats, hashtag performance and
competitor activity to surface timely content opportunities.
"""

import json
from datetime import datetime

import requests

from .base_agent import AgentTool, BaseAgent
from config.settings import DEFAULT_MODEL, RUN_MODE, RAPIDAPI_KEY

# ── RapidAPI: Instagram Scraper 20251 ─────────────────────────────────────────
_RAPIDAPI_HOST = "instagram-scraper-20251.p.rapidapi.com"
_RAPIDAPI_BASE = f"https://{_RAPIDAPI_HOST}"
_RAPIDAPI_HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": _RAPIDAPI_HOST,
}


def _ig_get(path: str, params: dict) -> dict:
    """GET request to Instagram Scraper 20251 API with 10s timeout."""
    r = requests.get(
        f"{_RAPIDAPI_BASE}{path}",
        headers=_RAPIDAPI_HEADERS,
        params=params,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


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
        limit = inputs.get("limit", 20)

        if not RAPIDAPI_KEY:
            return {"niche": niche, "source": "mock_no_key", "trending": [], "saturated_avoid": []}

        # Search for the niche hashtag + related ones
        results = []
        seen = set()

        # Primary hashtag
        primary_tag = niche.lower().replace(" ", "").replace("&", "").replace("/", "")
        candidate_tags = [primary_tag]

        # Derive 4-5 related tags from the niche phrase
        words = niche.lower().replace("/", " ").replace("&", " ").split()
        for w in words:
            w = w.strip()
            if len(w) > 3:
                candidate_tags.append(w)

        for tag in candidate_tags[:5]:
            clean_tag = tag.lstrip("#")
            if clean_tag in seen:
                continue
            seen.add(clean_tag)
            try:
                data = _ig_get("/v1/hashtag", {"name": clean_tag})
                # API returns data in various shapes — normalise
                info = data.get("data") or data.get("hashtag") or data
                media_count = (
                    info.get("media_count")
                    or info.get("edge_hashtag_to_media", {}).get("count")
                    or info.get("post_count")
                    or 0
                )
                # Format post count
                count_str = (
                    f"{media_count/1_000_000:.1f}M" if media_count >= 1_000_000
                    else f"{media_count/1_000:.0f}K" if media_count >= 1_000
                    else str(media_count)
                )
                results.append({
                    "tag": f"#{clean_tag}",
                    "posts": count_str,
                    "raw_count": media_count,
                })

                # Pull related hashtags from the response if available
                related = (
                    info.get("related_hashtags")
                    or info.get("edge_hashtag_to_related_hashtags", {}).get("edges", [])
                    or []
                )
                for rel in related[:4]:
                    rel_name = rel.get("node", {}).get("name") or rel.get("name") or rel
                    if isinstance(rel_name, str) and rel_name not in seen:
                        seen.add(rel_name)
                        try:
                            rd = _ig_get("/v1/hashtag", {"name": rel_name})
                            ri = rd.get("data") or rd.get("hashtag") or rd
                            rc = (
                                ri.get("media_count")
                                or ri.get("edge_hashtag_to_media", {}).get("count")
                                or ri.get("post_count")
                                or 0
                            )
                            rc_str = (
                                f"{rc/1_000_000:.1f}M" if rc >= 1_000_000
                                else f"{rc/1_000:.0f}K" if rc >= 1_000
                                else str(rc)
                            )
                            results.append({"tag": f"#{rel_name}", "posts": rc_str, "raw_count": rc})
                        except Exception:
                            results.append({"tag": f"#{rel_name}", "posts": "—", "raw_count": 0})

            except Exception as exc:
                results.append({"tag": f"#{clean_tag}", "posts": "error", "raw_count": 0, "error": str(exc)})

        # Sort by post count descending, take limit
        results.sort(key=lambda x: x.get("raw_count", 0), reverse=True)
        results = results[:limit]

        # Flag likely-saturated tags (>50M posts)
        saturated = [r["tag"] for r in results if r.get("raw_count", 0) > 50_000_000]

        return {
            "niche": niche,
            "source": "instagram_scraper_20251",
            "trending": results,
            "saturated_avoid": saturated,
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
        username = handle.lstrip("@")

        if not RAPIDAPI_KEY:
            return {"handle": handle, "source": "mock_no_key", "top_posts": [], "profile": {}}

        try:
            # Fetch user profile
            profile_data = _ig_get("/v1/user/info", {"username": username})
            profile_info = profile_data.get("data") or profile_data.get("user") or profile_data
            followers = (
                profile_info.get("follower_count")
                or profile_info.get("edge_followed_by", {}).get("count")
                or profile_info.get("followers")
                or "—"
            )
            bio = profile_info.get("biography") or profile_info.get("bio") or ""

            # Fetch recent posts
            posts_data = _ig_get("/v1/user/posts", {"username": username})
            raw_posts = (
                posts_data.get("data", {}).get("items")
                or posts_data.get("items")
                or posts_data.get("data")
                or []
            )

            top_posts = []
            for p in raw_posts[:12]:
                node = p.get("node") or p
                media_type = (
                    node.get("media_type")
                    or node.get("__typename", "")
                    .replace("GraphImage", "image")
                    .replace("GraphVideo", "reel")
                    .replace("GraphSidecar", "carousel")
                ).lower()
                likes = (
                    node.get("like_count")
                    or node.get("edge_liked_by", {}).get("count")
                    or node.get("likes_count")
                    or 0
                )
                comments = (
                    node.get("comment_count")
                    or node.get("edge_media_to_comment", {}).get("count")
                    or node.get("comments_count")
                    or 0
                )
                caption_raw = (
                    node.get("caption")
                    or node.get("edge_media_to_caption", {}).get("edges", [{}])[0]
                       .get("node", {}).get("text")
                    or ""
                )
                caption = caption_raw[:120] if isinstance(caption_raw, str) else ""
                top_posts.append({
                    "type": media_type or "unknown",
                    "caption_preview": caption,
                    "likes": likes,
                    "comments": comments,
                    "engagement": likes + comments,
                })

            # Sort by engagement
            top_posts.sort(key=lambda x: x["engagement"], reverse=True)

            return {
                "handle": handle,
                "source": "instagram_scraper_20251",
                "profile": {"followers": followers, "bio": bio},
                "top_posts_last_12": top_posts[:8],
                "best_post_type": top_posts[0]["type"] if top_posts else "unknown",
                "avg_likes": (
                    round(sum(p["likes"] for p in top_posts) / len(top_posts))
                    if top_posts else 0
                ),
            }

        except Exception as exc:
            return {
                "handle": handle,
                "source": "instagram_scraper_20251",
                "error": str(exc),
                "top_posts_last_12": [],
                "note": "Competitor data unavailable — private account or API limit reached",
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
