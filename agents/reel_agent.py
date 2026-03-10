"""
Reel / Short-Video Agent — The Director.

The most powerful growth tool. This agent produces a complete production
package for every Reel in the campaign — scene-by-scene breakdown,
text overlays, voiceover script, audio recommendations and shooting notes.
"""

import json

from .base_agent import AgentTool, BaseAgent
from config.settings import DEFAULT_MODEL, RUN_MODE


class ReelAgent(BaseAgent):
    PANEL_COLOR = "bold red"

    def __init__(self, **kwargs):
        super().__init__(
            name="Reel Agent  [Director]",
            model=DEFAULT_MODEL,
            use_thinking=False,
            **kwargs,
        )

    def get_system_prompt(self) -> str:
        return """You are a viral video director and Reel strategist who has produced
content that has generated millions of views on Instagram and TikTok.

You understand the algorithm deeply:
- First 2-3 seconds determine everything (hook rate → watch time → virality)
- Pattern interrupts stop the scroll: unexpected visuals, surprising text, movement
- Reels under 30 seconds perform best for reach; 60-90s for saves/shares
- Text overlays must work WITHOUT sound (60% of users watch on mute)
- Trending audio gives a 30-40% algorithmic boost

Your production packages include:
- Hook strategy (visual + text in first 3 seconds)
- Scene-by-scene breakdown (visual, text overlay, duration)
- Voiceover script (optional — works for educational/narrative content)
- Audio recommendations (trending track + backup)
- Shooting notes (equipment, angles, lighting)
- Editing notes (pace, transitions, effects)
- Thumbnail selection guidance

You write scripts that feel authentic, not produced — the "organic" feel outperforms
polished ads by 3-5x on organic reach."""

    def get_tools(self) -> list[AgentTool]:
        return [
            AgentTool(
                name="get_hook_templates",
                description="Get proven high-performing hook templates for a content type.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "content_category": {
                            "type": "string",
                            "description": "e.g. 'product_showcase', 'educational', 'process', 'pov_story'",
                        },
                        "emotion_target": {
                            "type": "string",
                            "description": "e.g. 'curiosity', 'awe', 'nostalgia', 'desire'",
                        },
                    },
                    "required": ["content_category"],
                },
                executor=self._get_hook_templates,
            ),
            AgentTool(
                name="get_trending_audio_recommendations",
                description="Get trending audio tracks suitable for a specific Reel mood.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "mood": {"type": "string"},
                        "duration_sec": {"type": "integer"},
                    },
                    "required": ["mood"],
                },
                executor=self._get_trending_audio,
            ),
        ]

    # ── Main run ───────────────────────────────────────────────────────────────

    def run(self, inputs: dict) -> dict:
        """
        inputs: {
            "post_brief": dict,
            "content_package": dict,
            "brand_profile": dict,
            "trend_report": dict
        }
        returns: reel_production_package dict
        """
        post = inputs["post_brief"]
        brand = inputs["brand_profile"]
        content = inputs.get("content_package", {})
        trends = inputs.get("trend_report", {})

        post_id = post.get("id", "unknown")

        # Only run for reels
        if post.get("type") != "reel":
            return {"post_id": post_id, "skipped": True, "reason": "Not a reel post"}

        self.print_header(f"Directing Reel production for {post_id}")

        if RUN_MODE == "demo":
            return self._demo_output(post, brand, content, trends)

        viral_formats = trends.get("viral_formats", [])
        reel_script_from_content = content.get("reel_script", {})

        prompt = f"""Create a complete Reel production package.

BRAND: {brand.get('name')}
BRAND VOICE: {brand.get('brand_voice', '')}
POST BRIEF: {json.dumps(post, indent=2)}
CONTENT HOOK: {content.get('caption', {}).get('hook', '')}
PRELIMINARY SCRIPT: {json.dumps(reel_script_from_content, indent=2)}

TRENDING FORMATS TO CONSIDER:
{json.dumps(viral_formats[:3], indent=2)}

Please:
1. Use get_hook_templates to identify the best hook strategy
2. Use get_trending_audio_recommendations for this Reel's mood
3. Build the complete production package

Output JSON:
```json
{{
  "post_id": "{post_id}",
  "reel_strategy": {{
    "format": "<which viral format this uses>",
    "target_duration_sec": <n>,
    "hook_strategy": "<why this hook will stop the scroll>",
    "emotion_arc": "<what viewer feels through the reel>"
  }},
  "production_script": {{
    "hook": {{
      "visual": "<exactly what viewer sees in first 3 seconds>",
      "text_overlay": "<text on screen — bold, short>",
      "audio_moment": "<what they hear>"
    }},
    "scenes": [
      {{
        "scene": 1,
        "duration_sec": <n>,
        "visual_description": "<what to film>",
        "camera_angle": "<angle/shot type>",
        "text_overlay": "<text on screen (if any)>",
        "transition": "<cut/zoom/whip>",
        "audio_note": "<specific audio moment>"
      }}
    ],
    "closing": {{
      "visual": "<final frame>",
      "text_overlay": "<CTA text>",
      "duration_sec": <n>
    }}
  }},
  "voiceover_script": "<full script if using voiceover, else null>",
  "audio": {{
    "primary_track": "<track name — artist>",
    "backup_track": "<fallback track>",
    "audio_start_point": "<start the track at X seconds in>",
    "volume_notes": "<how to mix audio>"
  }},
  "shooting_guide": {{
    "equipment": ["<item1>"],
    "shots_to_capture": ["<shot1>"],
    "lighting_setup": "<description>",
    "total_filming_time": "<estimated>"
  }},
  "editing_guide": {{
    "pace": "fast_cut|medium|slow_burn",
    "transitions": ["<transition1>"],
    "effects": ["<effect1>"],
    "colour_grade": "<grade instructions>",
    "caption_style": "<text style for overlays>",
    "total_editing_time": "<estimated>"
  }},
  "thumbnail_frame": "<which frame/second makes best thumbnail>",
  "predicted_performance": {{
    "reach_potential": "low|medium|high|viral",
    "primary_metric": "<what will drive results — saves/shares/comments>",
    "reasoning": "<why>"
  }}
}}
```"""

        raw = self.call_claude(prompt)
        package = self.extract_json(raw)
        if not package:
            package = {"raw_response": raw, "post_id": post_id}

        self.print_result("Target duration", f"{package.get('reel_strategy', {}).get('target_duration_sec', '?')}s")
        return package

    # ── Tool executors ─────────────────────────────────────────────────────────

    @staticmethod
    def _get_hook_templates(inputs: dict) -> dict:
        category = inputs.get("content_category", "product_showcase")
        templates = {
            "product_showcase": [
                "\"Wait until you see the final result...\" [show raw material first]",
                "\"POV: You just found the perfect [occasion] gift\" [product reveal]",
                "\"The [adjective] [product] you didn't know you needed\" [desire hook]",
            ],
            "educational": [
                "\"This [subject] fact will blow your mind\" [curiosity gap]",
                "\"[Number] things you didn't know about [topic]\" [listicle tease]",
                "\"The real reason [common belief is wrong]\" [myth-bust]",
            ],
            "process": [
                "\"[Raw material] to [finished product] in [time]\" [transformation]",
                "\"Here's what [X hours] of work looks like\" [effort reveal]",
                "\"ASMR: [craft process]\" [sensory hook]",
            ],
            "pov_story": [
                "\"POV: You discover [emotional scenario]\" [story drop]",
                "\"The day I [relatable moment]\" [narrative pull]",
                "\"Nobody talks about [hidden truth]\" [insider reveal]",
            ],
        }
        return {
            "category": category,
            "templates": templates.get(category, templates["product_showcase"]),
            "high_performing_openers": [
                "Extreme close-up that slowly pulls back (builds curiosity)",
                "Text-first hook before visual (stops silent scrollers)",
                "Unexpected movement in first frame (triggers startle reflex)",
            ],
        }

    @staticmethod
    def _get_trending_audio(inputs: dict) -> dict:
        mood = inputs.get("mood", "elegant")
        duration = inputs.get("duration_sec", 30)
        tracks = {
            "elegant": ["Hoppípolla — Sigur Rós", "Experience — Ludovico Einaudi"],
            "norse": ["Nordland — Wardruna", "Helvegen — Wardruna"],
            "energetic": ["Industry Baby — Lil Nas X", "MONTERO — Lil Nas X"],
            "nostalgic": ["Golden — Harry Styles", "Vienna — Billy Joel"],
            "asmr": ["Ambient Forest Sounds", "Rain on Stone"],
        }
        return {
            "mood": mood,
            "primary_track": tracks.get(mood, tracks["elegant"])[0],
            "backup_track": tracks.get(mood, tracks["elegant"])[-1],
            "usage_tip": f"Start track at 0:05 for the best beat drop alignment with your {duration}s reel",
        }

    # ── Demo output ────────────────────────────────────────────────────────────

    @staticmethod
    def _demo_output(post: dict, brand: dict, content: dict, trends: dict) -> dict:
        post_id = post.get("id", "post_1")
        existing_script = content.get("reel_script", {})
        scenes = existing_script.get("scenes", [])

        return {
            "post_id": post_id,
            "reel_strategy": {
                "format": "Before → After transformation (process reveal)",
                "target_duration_sec": 28,
                "hook_strategy": "Extreme close-up of hammer strike in frame 1 — movement + sound stops scroll. Text overlay creates curiosity gap before visual resolve.",
                "emotion_arc": "Curiosity → Awe (craft skill) → Desire (I want this) → Action (DM/comment)",
            },
            "production_script": {
                "hook": {
                    "visual": "EXTREME CLOSE-UP: Silver rod on steel anvil. Hammer swings down — sparks fly.",
                    "text_overlay": "Raw silver → Norse necklace in 60 seconds",
                    "audio_moment": "Wardruna drums hit at exact moment of hammer strike",
                },
                "scenes": scenes if scenes else [
                    {"scene": 1, "duration_sec": 3, "visual_description": "Close-up raw silver on anvil, hammer strikes", "camera_angle": "Macro, 45°", "text_overlay": "Raw silver.", "transition": "Hard cut", "audio_note": "Norse drum beat 1"},
                    {"scene": 2, "duration_sec": 5, "visual_description": "Cutting and shaping montage — hands working quickly", "camera_angle": "Overhead + side angles", "text_overlay": "14 hours of work.", "transition": "Jump cut x3", "audio_note": "Build — more percussion"},
                    {"scene": 3, "duration_sec": 5, "visual_description": "Close-up hand engraving Norse rune with fine tool", "camera_angle": "Macro — extreme close-up of tool on silver", "text_overlay": "A symbol used for 1200 years.", "transition": "Slow zoom out", "audio_note": "Strings enter"},
                    {"scene": 4, "duration_sec": 4, "visual_description": "Polishing cloth buffing silver to mirror shine", "camera_angle": "Close-up, reflection visible", "text_overlay": "Finished.", "transition": "Whip cut", "audio_note": "Music peaks"},
                    {"scene": 5, "duration_sec": 4, "visual_description": "Necklace placed in branded box, tissue paper", "camera_angle": "Top-down overhead", "text_overlay": "Handmade. Not mass produced.", "transition": "Slow fade", "audio_note": "Softer"},
                    {"scene": 6, "duration_sec": 4, "visual_description": "Model wearing necklace — looks at camera, smiles", "camera_angle": "Portrait, shallow DOF", "text_overlay": "DM us CRAFT ✉️", "transition": "Fade out", "audio_note": "Gentle close"},
                ],
                "closing": {
                    "visual": "Logo lockup over dark navy background",
                    "text_overlay": f"DM CRAFT · {brand.get('instagram_handle', '@brand')}",
                    "duration_sec": 3,
                },
            },
            "voiceover_script": None,
            "audio": {
                "primary_track": "Nordland — Wardruna (Nordic folk — perfect for Norse brand)",
                "backup_track": "Hoppípolla — Sigur Rós",
                "audio_start_point": "Start track at 0:08 (after intro builds) — first drum hit aligns with hammer strike",
                "volume_notes": "Music at 70% — ambient anvil/hammer sounds layered at 30%",
            },
            "shooting_guide": {
                "equipment": [
                    "iPhone 15 Pro / DSLR with macro lens (100mm)",
                    "Tripod + overhead arm rig",
                    "Ring light or softbox — positioned at 45° left",
                    "Lavalier mic (if doing voiceover)",
                ],
                "shots_to_capture": [
                    "Macro: hammer on silver (10+ takes — different angles)",
                    "Overhead: full process from above",
                    "Side-angle: hand and tool working",
                    "Macro: rune engraving tool on silver surface",
                    "Polishing reflection close-up",
                    "Final product: necklace held up, product in box, being worn",
                ],
                "lighting_setup": "Diffused natural light + LED ring fill. No harsh shadows on silver (use bounce card).",
                "total_filming_time": "2-3 hours of shooting process → 28 second reel",
            },
            "editing_guide": {
                "pace": "fast_cut",
                "transitions": ["Hard cut", "Jump cut (3x for speed effect)", "Slow motion pull-back", "Whip cut"],
                "effects": ["Slight desaturation on silver shots for cinematic feel", "Warm tone lift on final reveal"],
                "colour_grade": "+warmth 8, -saturation 5, +clarity 10, vignette subtle",
                "caption_style": "White sans-serif, bold, centred. Drop shadow for readability on all backgrounds.",
                "total_editing_time": "90-120 minutes in CapCut or Premiere Pro",
            },
            "thumbnail_frame": "Scene 4 — polished necklace gleaming (second 15). Maximum visual impact + clear product.",
            "predicted_performance": {
                "reach_potential": "high",
                "primary_metric": "shares + saves (educative + aspirational combo)",
                "reasoning": "Process reels in the craft niche consistently outperform other formats by 2-4x. Norse audio trend + transformation format = strong algorithmic signal.",
            },
        }
