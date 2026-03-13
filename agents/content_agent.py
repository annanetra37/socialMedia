"""
Content Generation Agent — The Copywriter.

Takes a campaign post brief and generates:
- Caption with hook, body, and CTA
- Hashtag set (primary + niche)
- Carousel slide copy (if applicable)
- Reel script (if applicable)
- Alt text for accessibility
"""

import json
import re

from .base_agent import AgentTool, BaseAgent
from config.settings import DEFAULT_MODEL, RUN_MODE


def _brand_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _product_image_context(brand: dict) -> str:
    """Build a product image reference block for the agent prompt."""
    products = brand.get("products", [])
    if not products:
        return ""
    slug = _brand_slug(brand.get("name", "brand"))
    lines = [
        "BRAND PRODUCT PHOTOS (real uploaded images — use these as primary visuals):",
        "These are NOT just for product posts. Use them for lifestyle shots, before/after,",
        "educational carousels, unboxing reels, and any post where showing the product adds value.",
    ]
    for i, p in enumerate(products):
        price = f"${p['price_usd']}" if p.get("price_usd") else "price unlisted"
        lines.append(f"  [{i}] {p.get('name', 'Product')} — {price}")
        lines.append(f"       photo URL: /api/brands/{slug}/products/{i}/image")
    return "\n".join(lines)


class ContentAgent(BaseAgent):
    PANEL_COLOR = "bold yellow"

    def __init__(self, **kwargs):
        super().__init__(
            name="Content Agent  [Copywriter]",
            model=DEFAULT_MODEL,
            use_thinking=False,
            **kwargs,
        )

    def get_system_prompt(self) -> str:
        return """You are an elite social media copywriter who specialises in Instagram content.

Your writing style:
- Opens with a PATTERN-INTERRUPT hook (first line stops the scroll)
- Uses the AIDA framework: Attention → Interest → Desire → Action
- Writes conversationally — never corporate or stiff
- Uses strategic line breaks for mobile readability
- Emoji used sparingly — for emphasis, not decoration
- CTAs are specific and low-friction ("Comment X", "Save this", "DM us Y")

For captions you always structure:
Line 1: Hook (pattern interrupt — makes them stop scrolling)
Lines 2-4: The story / value / emotion
Line 5-6: CTA + hashtags

For carousels you write:
- Slide 1: Hook (the promise)
- Slides 2-N: The value / story
- Last slide: CTA

For reels you write:
- Opening hook (first 2 seconds — what they see AND hear)
- Scene sequence
- Text overlays
- Spoken voiceover (if any)
- Closing CTA

You adapt tone precisely to each brand's voice."""

    def get_tools(self) -> list[AgentTool]:
        return [
            AgentTool(
                name="get_hashtag_set",
                description="Generate an optimised hashtag set for a post.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "content_type": {"type": "string", "description": "reel/carousel/image"},
                        "topic": {"type": "string"},
                        "niche": {"type": "string"},
                        "brand_hashtags": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["content_type", "topic", "niche"],
                },
                executor=self._get_hashtag_set,
            ),
            AgentTool(
                name="check_caption_length",
                description="Check caption character count and readability score.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "caption": {"type": "string"},
                    },
                    "required": ["caption"],
                },
                executor=self._check_caption_length,
            ),
        ]

    # ── Main run ───────────────────────────────────────────────────────────────

    def run(self, inputs: dict) -> dict:
        """
        inputs: {
            "post_brief": dict  (single post from campaign plan),
            "brand_profile": dict,
            "strategy_plan": dict,
            "languages": list[str] (optional),
            "available_photo_indices": list[int] (optional — unused product photo indices)
        }
        returns: content_package dict
        """
        post = inputs["post_brief"]
        brand = inputs["brand_profile"]
        strategy = inputs.get("strategy_plan", {})
        languages = inputs.get("languages") or brand.get("languages") or ["English"]
        available_photos = inputs.get("available_photo_indices")

        post_id = post.get("id", "unknown")
        post_type = (post.get("type") or "post").lower()
        self.print_header(f"Generating content for {post_id} — {post_type.upper()} — languages: {', '.join(languages)}")

        if RUN_MODE == "demo":
            return self._demo_output(post, brand)

        products = brand.get("products", [])
        slug = _brand_slug(brand.get("name", "brand"))

        # ── For image posts: select a specific unused product photo ──────────
        photo_instruction = ""
        selected_idx = None
        if post_type == "image" and products and available_photos is not None:
            if available_photos:
                selected_idx = available_photos[0]
            else:
                selected_idx = 0  # fallback if somehow empty

            p = products[selected_idx] if selected_idx < len(products) else products[0]
            photo_url = f"/api/brands/{slug}/products/{selected_idx}/image"
            price_str = f"${p.get('price_usd', p.get('price_eur', ''))}" if p.get("price_usd") or p.get("price_eur") else "price unlisted"
            photo_instruction = f"""
ASSIGNED PRODUCT PHOTO (you MUST write content specifically about this product):
  Product: {p.get('name', 'Product')}
  Price: {price_str}
  Photo URL: {photo_url}
  Bestseller: {"Yes" if p.get("bestseller") else "No"}

Write the caption, hook, and CTA to match THIS specific product and its photo.
The content should feel natural and authentic — as if written while looking at the photo.
Include the product name in the caption. Reference visual details a viewer would see.
Add "selected_product_idx": {selected_idx} and "selected_product_photo_url": "{photo_url}" in your JSON output.
"""
        product_ctx = _product_image_context(brand) if not photo_instruction else ""

        lang_instruction = ""
        if len(languages) == 1:
            lang_instruction = f"\nLANGUAGE: Write ALL content (caption, hook, CTA, hashtags) in {languages[0]}.\n"
        elif len(languages) > 1:
            lang_instruction = f"\nLANGUAGES: Generate the full content package in EACH of these languages: {', '.join(languages)}.\nFor multi-language output, include a top-level \"languages\" object keyed by language name, each containing the full caption/hashtags/carousel/reel content in that language. The first language ({languages[0]}) should also populate the top-level fields.\n"

        prompt = f"""Write complete social media content for this post brief.

BRAND: {brand.get('name')}
BRAND VOICE: {brand.get('brand_voice', '')}
BRAND VALUES: {', '.join(brand.get('brand_values', []))}
AUDIENCE: {json.dumps(brand.get('target_audience', {}), indent=2)}
{product_ctx}
{photo_instruction}
{lang_instruction}
POST BRIEF:
{json.dumps(post, indent=2)}

APPROVED HOOKS from strategy:
{json.dumps(strategy.get('growth_strategy', {}).get('viral_hooks', []), indent=2)}

APPROVED CTAs:
{json.dumps(strategy.get('growth_strategy', {}).get('cta_templates', []), indent=2)}

Please:
1. Use get_hashtag_set to get the optimised hashtag set
2. Write the full content package
3. Use check_caption_length to verify the caption is ideal length

Output JSON:
```json
{{
  "post_id": "{post_id}",
  "post_type": "{post.get('type', 'post')}",
  "caption": {{
    "hook": "<first line — scroll stopper>",
    "body": "<story / value lines>",
    "cta": "<specific call to action>",
    "full_caption": "<complete caption ready to post>",
    "character_count": <n>
  }},
  "hashtags": {{
    "primary": ["<tag>"],
    "secondary": ["<tag>"],
    "niche": ["<tag>"],
    "full_set": "<all hashtags as one string>"
  }},
  "carousel_slides": [
    {{"slide_number": 1, "headline": "<>", "body": "<>", "visual_note": "<>"}}
  ],
  "reel_script": {{
    "hook_visual": "<what viewer sees in first 2s>",
    "hook_text_overlay": "<text on screen>",
    "scenes": [
      {{"scene": 1, "duration_sec": <n>, "visual": "<>", "text_overlay": "<>", "audio_note": "<>"}}
    ],
    "voiceover": "<full voiceover script if applicable>",
    "closing_cta": "<final screen text>"
  }},
  "alt_text": "<accessibility description>",
  "best_time_to_post": "<HH:MM>",
  "selected_product_idx": "<index of the product photo used, or null>",
  "selected_product_photo_url": "<URL of the product photo used, or null>",
  "content_notes": "<any production notes for creator>"
}}
```
Note: carousel_slides only if type is 'carousel'. reel_script only if type is 'reel'.
Note: selected_product_idx and selected_product_photo_url only if a specific product photo was assigned."""

        raw = self.call_claude(prompt)
        content = self.extract_json(raw)
        if not content:
            content = {"raw_response": raw, "post_id": post_id}

        # Ensure the selected photo is recorded even if Claude didn't output it
        if selected_idx is not None:
            content.setdefault("selected_product_idx", selected_idx)
            content.setdefault("selected_product_photo_url", f"/api/brands/{slug}/products/{selected_idx}/image")

        self.print_result("Caption hook", content.get("caption", {}).get("hook", "")[:60])
        return content

    # ── Tool executors ─────────────────────────────────────────────────────────

    @staticmethod
    def _get_hashtag_set(inputs: dict) -> dict:
        niche = inputs.get("niche", "jewellery")
        content_type = inputs.get("content_type", "post")

        base_tags = ["#nordicjewellery", "#handmadejewellery", "#silversmith"]
        content_tags = {
            "reel": ["#instareels", "#reelsinstagram", "#reelsvideo"],
            "carousel": ["#infographic", "#didyouknow", "#learnontiktok"],
            "image": ["#flatlayoftheday", "#productphotography", "#jewelleryphoto"],
        }.get(content_type, [])

        return {
            "primary": base_tags[:3],
            "secondary": ["#vikingfashion", "#artisanjewellery", "#slowfashion"],
            "niche": ["#ethicaljewellery", "#sustainablejewellery", "#norsestyle"],
            "content_specific": content_tags,
            "full_set": " ".join(base_tags + content_tags + ["#ethicaljewellery", "#sustainablejewellery"]),
        }

    @staticmethod
    def _check_caption_length(inputs: dict) -> dict:
        caption = inputs.get("caption", "")
        length = len(caption)
        return {
            "character_count": length,
            "word_count": len(caption.split()),
            "status": "optimal" if 150 <= length <= 400 else ("too_short" if length < 150 else "too_long"),
            "recommendation": "Ideal Instagram caption: 150-400 characters" if length < 150 or length > 400 else "Perfect length",
        }

    # ── Demo output ────────────────────────────────────────────────────────────

    @staticmethod
    def _demo_output(post: dict, brand: dict) -> dict:
        post_type = post.get("type", "image")
        post_id = post.get("id", "post_1")

        base = {
            "post_id": post_id,
            "post_type": post_type,
            "caption": {
                "hook": post.get("hook", "\"This changes everything...\""),
                "body": (
                    f"Every piece we make at {brand.get('name', 'our studio')} "
                    "starts as raw silver and ends as a story worth wearing.\n\n"
                    "Handcrafted using traditional Nordic techniques passed down through generations.\n\n"
                    "No shortcuts. No mass production. Just pure craftsmanship."
                ),
                "cta": post.get("cta", "Save this if you appreciate slow craftsmanship →"),
                "full_caption": (
                    post.get("hook", '"Every piece tells a story..."')
                    + "\n\nEvery piece we make at "
                    + brand.get("name", "our studio")
                    + " starts as raw silver and ends as a story worth wearing.\n\n"
                    "Handcrafted using traditional Nordic techniques passed down through generations.\n\n"
                    "No shortcuts. No mass production. Just pure craftsmanship.\n\n"
                    + post.get("cta", "Comment CRAFT below if this resonates \u2192")
                ),
                "character_count": 420,
            },
            "hashtags": {
                "primary": ["#nordicjewellery", "#handmadejewellery", "#silversmith"],
                "secondary": ["#vikingfashion", "#artisanjewellery", "#scandinaviandesign"],
                "niche": ["#ethicaljewellery", "#slowjewellery", "#norsestyle"],
                "full_set": "#nordicjewellery #handmadejewellery #silversmith #vikingfashion #artisanjewellery #scandinaviandesign #ethicaljewellery #slowjewellery #norsestyle",
            },
            "alt_text": f"Handcrafted {brand.get('name', '')} silver jewellery with Norse runic design on white marble background",
            "best_time_to_post": post.get("time", "18:00"),
            "content_notes": post.get("visual_notes", ""),
        }

        if post_type == "carousel":
            base["carousel_slides"] = [
                {"slide_number": 1, "headline": "7 Norse Rune Symbols — and what they mean", "body": "Swipe to discover the meaning behind each ancient symbol →", "visual_note": "Hero rune necklace on marble"},
                {"slide_number": 2, "headline": "ᚠ Fehu — Wealth & Prosperity", "body": "The Fehu rune was worn by Norse merchants seeking abundance. Today it symbolises the courage to build.", "visual_note": "Close-up of Fehu rune engraving"},
                {"slide_number": 3, "headline": "ᚨ Ansuz — Wisdom & Communication", "body": "Sacred to Odin. Warriors inscribed this rune before battle — seeking clarity of mind.", "visual_note": "Ansuz pendant macro shot"},
                {"slide_number": 4, "headline": "ᛉ Algiz — Protection", "body": "The most powerful protective rune. Worn by those who seek to guard what they love most.", "visual_note": "Algiz necklace worn by model"},
                {"slide_number": 5, "headline": "Which rune speaks to you?", "body": "Each piece in our Nordic collection carries one of these ancient symbols. DM us RUNE to find yours.", "visual_note": "Full collection flat lay. Strong CTA overlay."},
            ]

        if post_type == "reel":
            base["reel_script"] = {
                "hook_visual": "Extreme close-up: hammer strikes silver — sparks fly",
                "hook_text_overlay": "Raw silver → Norse necklace in 60 seconds",
                "scenes": [
                    {"scene": 1, "duration_sec": 3, "visual": "Close-up raw silver rod on anvil", "text_overlay": "It starts here.", "audio_note": "Wardruna intro — Norse drums building"},
                    {"scene": 2, "duration_sec": 8, "visual": "Timelapse: cutting, shaping, hammering silver", "text_overlay": "14 hours of work.", "audio_note": "Audio builds — hammer sounds layered with music"},
                    {"scene": 3, "duration_sec": 5, "visual": "Hand engraving Norse rune into silver", "text_overlay": "A 1200-year-old symbol.", "audio_note": "Music swells"},
                    {"scene": 4, "duration_sec": 4, "visual": "Polish and finishing — necklace gleaming", "text_overlay": "Finished.", "audio_note": "Music peaks"},
                    {"scene": 5, "duration_sec": 4, "visual": "Necklace placed in branded box", "text_overlay": "Handmade. Not mass produced.", "audio_note": "Music fades"},
                    {"scene": 6, "duration_sec": 3, "visual": "Model wearing finished necklace — confident smile", "text_overlay": "DM us CRAFT ✉️", "audio_note": "Gentle close"},
                ],
                "voiceover": None,
                "closing_cta": "DM us CRAFT for your handmade Norse piece",
            }

        return base
