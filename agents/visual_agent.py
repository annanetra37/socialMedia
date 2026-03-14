"""
Visual Generation Agent — The Art Director.

Takes a post brief and generates detailed visual direction:
- Image generation prompts (for DALL-E / Midjourney / Stable Diffusion)
- Carousel design specs
- Colour palette and typography guidance
- Photography brief (if using real photography)
- Canva template recommendations
"""

import json

from .base_agent import AgentTool, BaseAgent
from agents.content_agent import _brand_slug, _product_image_context
from config.settings import DEFAULT_MODEL, OPENAI_API_KEY, RUN_MODE


class VisualAgent(BaseAgent):
    PANEL_COLOR = "bold cyan"

    def __init__(self, **kwargs):
        super().__init__(
            name="Visual Agent  [Art Director]",
            model=DEFAULT_MODEL,
            use_thinking=False,
            **kwargs,
        )

    def get_system_prompt(self) -> str:
        return """You are a world-class art director and visual content strategist for social media.

Your expertise spans:
- AI image generation (Midjourney, DALL-E, Stable Diffusion) — you write precise prompts
- Photography direction — lighting, composition, styling
- Carousel design — layout, typography, colour theory
- Brand visual consistency — every asset strengthens the brand world
- Instagram aesthetic — grid planning, story design, Reel thumbnails

When creating visual direction you:
1. Understand the brand's visual identity deeply (colours, fonts, mood, aesthetic)
2. Translate content briefs into precise, actionable visual specs
3. Write AI generation prompts that are detailed and replicable
4. Provide backup instructions for human photographers/designers
5. Ensure visual consistency across all posts

You always think about: lighting, composition, colour palette, props, model direction,
text placement, and how the visual looks as a thumbnail at 50x50px."""

    def get_tools(self) -> list[AgentTool]:
        return [
            AgentTool(
                name="generate_image_prompt",
                description="Generate a detailed AI image generation prompt for Midjourney/DALL-E.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string"},
                        "style": {"type": "string"},
                        "mood": {"type": "string"},
                        "platform": {"type": "string", "enum": ["midjourney", "dalle3", "stable_diffusion"]},
                    },
                    "required": ["subject", "style", "mood"],
                },
                executor=self._generate_image_prompt,
            ),
            AgentTool(
                name="get_brand_visual_guidelines",
                description="Retrieve brand colour palette, typography and visual style rules.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "brand_name": {"type": "string"},
                    },
                    "required": ["brand_name"],
                },
                executor=self._get_brand_visual_guidelines,
            ),
            AgentTool(
                name="generate_dalle_image",
                description="Actually generate an image using DALL-E 3 (requires OPENAI_API_KEY).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string"},
                        "size": {
                            "type": "string",
                            "enum": ["1024x1024", "1024x1792", "1792x1024"],
                            "default": "1024x1024",
                        },
                    },
                    "required": ["prompt"],
                },
                executor=self._generate_dalle_image,
            ),
        ]

    # ── Main run ───────────────────────────────────────────────────────────────

    def run(self, inputs: dict) -> dict:
        """
        inputs: {
            "post_brief": dict,
            "content_package": dict,
            "brand_profile": dict
        }
        returns: visual_package dict
        """
        post = inputs["post_brief"]
        brand = inputs["brand_profile"]
        content = inputs.get("content_package", {})

        post_id = post.get("id", "unknown")
        self.print_header(f"Creating visual direction for {post_id}")

        if RUN_MODE == "demo":
            return self._demo_output(post, brand, content)

        # ── Decide primary image source ────────────────────────────────────────
        # If the content agent already selected a specific product photo, use it.
        # Otherwise, if the brand has uploaded product photos, use them.
        # DALL-E is only used when no real photos are available.
        products = brand.get("products", [])
        has_product_photos = bool(products)
        selected_idx = content.get("selected_product_idx")
        selected_url = content.get("selected_product_photo_url")

        if selected_idx is not None and selected_url:
            # Content agent already picked a specific photo — tell visual agent to use it
            p = products[selected_idx] if selected_idx < len(products) else {}
            product_photo_block = (
                f"ASSIGNED PRODUCT PHOTO (Content Agent selected this — use it as primary image):\n"
                f"  Product: {p.get('name', 'Product')}\n"
                f"  Photo URL: {selected_url}\n"
                f"  Index: {selected_idx}"
            )
            dalle_instruction = (
                f"The Content Agent already selected product photo [{selected_idx}] for this post. "
                f"Set primary_image.product_photo_url to \"{selected_url}\". "
                "Do NOT call generate_dalle_image. "
                "Only call generate_image_prompt to write a backup AI prompt description."
            )
        elif has_product_photos:
            slug = _brand_slug(brand.get("name", "brand"))
            # Build the product list for the prompt (same as content agent context)
            product_lines = []
            for i, p in enumerate(products):
                price = f"${p['price_usd']}" if p.get("price_usd") else "unlisted"
                product_lines.append(
                    f"  [{i}] {p.get('name','Product')} ({price}) → /api/brands/{slug}/products/{i}/image.jpg"
                )
            product_photo_block = (
                "UPLOADED PRODUCT PHOTOS (use these as primary_image.product_photo_url):\n"
                + "\n".join(product_lines)
            )
            dalle_instruction = (
                "The brand has real product photos (listed above). "
                "Do NOT call generate_dalle_image. "
                "Set primary_image.product_photo_url to the most relevant photo URL above. "
                "Only call generate_image_prompt to write an AI prompt as a backup description."
            )
        else:
            product_photo_block = ""
            dalle_instruction = (
                "No product photos are uploaded. "
                "Call generate_dalle_image to create the primary visual asset if OPENAI_API_KEY is available."
            )

        product_ctx = _product_image_context(brand)
        prompt = f"""Create complete visual direction for this social media post.

BRAND: {brand.get('name')}
BRAND VOICE: {brand.get('brand_voice', '')}
POST TYPE: {post.get('type', 'image')}
CONTENT BRIEF: {post.get('content_brief', '')}
VISUAL NOTES FROM PLANNER: {post.get('visual_notes', '')}
CAPTION HOOK: {content.get('caption', {}).get('hook', '')}
{product_photo_block}

IMAGE SOURCE INSTRUCTION: {dalle_instruction}

Please:
1. Use get_brand_visual_guidelines to get colour and typography rules
2. Use generate_image_prompt to create a backup AI prompt (always useful for designers)
3. {"Set primary_image.product_photo_url from the list above — skip generate_dalle_image" if has_product_photos else "Use generate_dalle_image for the primary asset if OPENAI_API_KEY is available"}

Output JSON:
```json
{{
  "post_id": "{post_id}",
  "post_type": "{post.get('type', 'image')}",
  "primary_image": {{
    "description": "<what to create or what the photo shows>",
    "product_photo_url": "<URL from uploaded product photos above, or null if none>",
    "ai_generation_prompt": "<full Midjourney/DALL-E prompt>",
    "photography_brief": "<direction for real photographer>",
    "dimensions": "<WxH>",
    "generated_url": "<url if DALL-E generated, else null>"
  }},
  "carousel_slides_design": [
    {{
      "slide": 1,
      "background": "<colour/image>",
      "layout": "<description>",
      "headline_style": "<font, size, colour>",
      "body_style": "<font, size, colour>",
      "elements": ["<element1>"]
    }}
  ],
  "colour_palette": {{
    "primary": "<hex>",
    "secondary": "<hex>",
    "accent": "<hex>",
    "background": "<hex>",
    "text": "<hex>"
  }},
  "typography": {{
    "headline_font": "<font name>",
    "body_font": "<font name>"
  }},
  "thumbnail_notes": "<how the thumbnail looks at small size>",
  "grid_notes": "<how this fits into the Instagram grid aesthetic>",
  "production_checklist": ["<item1>", "<item2>"]
}}
```"""

        raw = self.call_claude(prompt)
        visual = self.extract_json(raw)
        if not visual:
            visual = {"raw_response": raw, "post_id": post_id}

        self.print_result("AI prompt generated", bool(visual.get("primary_image", {}).get("ai_generation_prompt")))
        return visual

    # ── Tool executors ─────────────────────────────────────────────────────────

    @staticmethod
    def _generate_image_prompt(inputs: dict) -> dict:
        subject = inputs.get("subject", "jewellery")
        style = inputs.get("style", "minimal, elegant")
        mood = inputs.get("mood", "luxurious")
        platform = inputs.get("platform", "midjourney")

        if platform == "midjourney":
            prompt = (
                f"{subject}, {style}, {mood} mood, "
                "white marble surface, natural daylight, macro photography, "
                "shallow depth of field, editorial style, "
                "8K resolution, highly detailed --ar 1:1 --v 6.1 --style raw"
            )
        else:  # dalle3
            prompt = (
                f"Professional product photography of {subject}. "
                f"Style: {style}. Mood: {mood}. "
                "White marble background, soft natural light from the left, "
                "minimal composition, luxury jewellery editorial aesthetic. "
                "High resolution, sharp focus."
            )

        return {"platform": platform, "prompt": prompt}

    @staticmethod
    def _get_brand_visual_guidelines(inputs: dict) -> dict:
        return {
            "colour_palette": {
                "primary": "#1A1A2E",       # Deep Nordic navy
                "secondary": "#C0A882",     # Warm silver/champagne
                "accent": "#8B7355",        # Antique gold
                "background": "#F9F7F4",    # Off-white parchment
                "text": "#2C2C2C",          # Near-black
            },
            "typography": {
                "headline_font": "Cormorant Garamond (serif — elegant)",
                "body_font": "Inter (clean, readable)",
                "font_weight_headline": "300 or 600",
                "font_weight_body": "400",
            },
            "photography_style": {
                "lighting": "Soft natural light — golden hour or overcast",
                "backgrounds": ["white marble", "raw linen", "dark slate", "Nordic forest moss"],
                "props": ["dried flowers", "aged wood", "leather cord", "pine cones"],
                "avoid": ["plastic props", "cheap backgrounds", "over-editing", "heavy filters"],
            },
            "instagram_grid_aesthetic": "Alternating light/dark posts — creating a woven pattern",
            "story_templates": "Dark navy background with champagne text and silver border",
        }

    @staticmethod
    def _generate_dalle_image(inputs: dict) -> dict:
        if not OPENAI_API_KEY:
            return {"status": "skipped", "reason": "OPENAI_API_KEY not configured", "url": None}
        try:
            import requests
            resp = requests.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": "dall-e-3",
                    "prompt": inputs.get("prompt", ""),
                    "size": inputs.get("size", "1024x1024"),
                    "quality": "hd",
                    "n": 1,
                },
                timeout=60,
            )
            data = resp.json()
            url = data.get("data", [{}])[0].get("url", None)
            return {"status": "generated", "url": url}
        except Exception as e:
            return {"status": "error", "reason": str(e), "url": None}

    # ── Demo output ────────────────────────────────────────────────────────────

    @staticmethod
    def _demo_output(post: dict, brand: dict, content: dict) -> dict:
        post_type = post.get("type", "image")
        post_id = post.get("id", "post_1")

        slide_designs = []
        if post_type == "carousel":
            for i, slide in enumerate(content.get("carousel_slides", [])[:5], 1):
                slide_designs.append({
                    "slide": i,
                    "background": "#F9F7F4" if i % 2 != 0 else "#1A1A2E",
                    "layout": "Centre-aligned headline + body text. Brand logo bottom-right.",
                    "headline_style": "Cormorant Garamond 32px, #1A1A2E" if i % 2 != 0 else "Cormorant Garamond 32px, #C0A882",
                    "body_style": "Inter 16px, #2C2C2C" if i % 2 != 0 else "Inter 16px, #F9F7F4",
                    "elements": ["Rune symbol illustration (top)", slide.get("visual_note", "Product image")],
                })

        reel_thumb = None
        if post_type == "reel":
            reel_thumb = "Frame at 0:04 — hammer striking silver with sparks. Maximum visual impact."

        return {
            "post_id": post_id,
            "post_type": post_type,
            "primary_image": {
                "description": post.get("visual_notes", "Product beauty shot on marble"),
                "ai_generation_prompt": (
                    f"{brand.get('name', 'brand')} silver jewellery with Norse runic engravings, "
                    "elegant minimal composition, white marble surface, soft natural window light, "
                    "macro photography, shallow depth of field, editorial luxury style, "
                    "8K resolution --ar 1:1 --v 6.1 --style raw"
                ),
                "photography_brief": (
                    "Set up on white marble tile. Diffused natural light from left window. "
                    "Macro lens, f/2.8. Position necklace at rule-of-thirds intersection. "
                    "Add single dried flower sprig as prop. Shoot 20+ frames."
                ),
                "dimensions": "1080x1080" if post_type != "reel" else "1080x1920",
                "generated_url": None,
            },
            "carousel_slides_design": slide_designs,
            "reel_thumbnail": reel_thumb,
            "colour_palette": {
                "primary": "#1A1A2E",
                "secondary": "#C0A882",
                "accent": "#8B7355",
                "background": "#F9F7F4",
                "text": "#2C2C2C",
            },
            "typography": {
                "headline_font": "Cormorant Garamond",
                "body_font": "Inter",
            },
            "thumbnail_notes": "Main jewellery piece must be clearly visible at 50x50px — avoid busy backgrounds on first frame.",
            "grid_notes": "This is a LIGHT post. Position after the dark reel to maintain alternating grid pattern.",
            "production_checklist": [
                "Shoot on white marble tile (not fabric)",
                "Use diffused natural light — no artificial light",
                "Clean the jewellery before shooting",
                "Shoot RAW format, minimum 3 compositions",
                "Include 1 close-up macro and 1 wider lifestyle shot",
                "Edit to brand colour grade (+warmth, -saturation)",
            ],
        }
