"""
Engagement Agent — The Community Manager.

Handles the daily engagement block:
- Replies to comments (general, questions, compliments)
- Qualifies and responds to DM enquiries
- Identifies potential leads from comments and flags them
- Follows up on previous conversations
- Generates proactive community engagement actions
"""

import json
from datetime import datetime

from .base_agent import AgentTool, BaseAgent
from config.settings import DEFAULT_MODEL, RUN_MODE


class EngagementAgent(BaseAgent):
    PANEL_COLOR = "bold green"

    def __init__(self, **kwargs):
        super().__init__(
            name="Engagement Agent  [Community Manager]",
            model=DEFAULT_MODEL,
            use_thinking=False,
            **kwargs,
        )

    def get_system_prompt(self) -> str:
        return """You are a warm, knowledgeable community manager for a premium handcrafted brand.

Your engagement philosophy:
- Every comment is an opportunity to deepen a relationship, not just get a like
- Speed matters: respond within 2 hours for maximum algorithmic benefit
- Be human first, salesperson never — authentic responses build trust
- Turn price questions into conversations about value and craft
- Identify high-intent buyers (asking price, asking about customisation, tagging friends)
- Use the brand's first name in some replies but never over-personalise

Response rules:
1. Comments asking price → acknowledge, give a value frame, then DM invite
2. Compliments → thank genuinely, add a tiny story detail, invite engagement
3. Questions about process → educate briefly, invite them to "DM for more"
4. Negative comments → acknowledge, empathise, resolve offline (DM)
5. Lead comments → flag as HOT LEAD, draft a personalised qualifying DM

Tone: Warm, knowledgeable, proud-but-humble. Never pushy. Never robotic."""

    def get_tools(self) -> list[AgentTool]:
        return [
            AgentTool(
                name="fetch_pending_comments",
                description="Fetch unanswered comments from recent posts.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "posts_limit": {"type": "integer", "default": 10, "description": "Recent posts to check"},
                        "hours_back": {"type": "integer", "default": 24},
                    },
                    "required": [],
                },
                executor=self._fetch_pending_comments,
            ),
            AgentTool(
                name="fetch_pending_dms",
                description="Fetch unanswered DMs in the inbox.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20},
                    },
                    "required": [],
                },
                executor=self._fetch_pending_dms,
            ),
            AgentTool(
                name="classify_engagement_intent",
                description="Classify a comment or DM by intent: buyer/enquiry/compliment/question/negative.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                    },
                    "required": ["text"],
                },
                executor=self._classify_intent,
            ),
        ]

    # ── Main run ───────────────────────────────────────────────────────────────

    def run(self, inputs: dict) -> dict:
        """
        inputs: {
            "brand_profile": dict,
            "incoming_comments": list[dict] (optional — will fetch if not provided),
            "incoming_dms": list[dict] (optional),
            "products": list[dict] (optional)
        }
        returns: engagement_responses dict
        """
        brand = inputs["brand_profile"]
        comments = inputs.get("incoming_comments", [])
        dms = inputs.get("incoming_dms", [])

        self.print_header("Processing engagement queue")

        if RUN_MODE == "demo":
            return self._demo_output(brand)

        comments_str = json.dumps(comments[:20], indent=2) if comments else "Use fetch_pending_comments tool"
        dms_str = json.dumps(dms[:10], indent=2) if dms else "Use fetch_pending_dms tool"

        prompt = f"""Process today's engagement queue for {brand.get('name')}.

BRAND: {brand.get('name')}
BRAND VOICE: {brand.get('brand_voice', '')}
PRODUCTS: {json.dumps(brand.get('products', []), indent=2)}

Please:
1. Use fetch_pending_comments to get unanswered comments
2. Use fetch_pending_dms to get unanswered DMs
3. Use classify_engagement_intent for each item to prioritise
4. Write personalised replies for all items

Output JSON:
```json
{{
  "processed_at": "{datetime.now().isoformat()}",
  "comment_replies": [
    {{
      "comment_id": "<id>",
      "username": "<@user>",
      "original_comment": "<text>",
      "intent": "buyer|enquiry|compliment|question|negative",
      "priority": "high|medium|low",
      "reply": "<your reply text>",
      "action": "replied|flagged_lead|escalate_to_dm"
    }}
  ],
  "dm_replies": [
    {{
      "dm_id": "<id>",
      "username": "<@user>",
      "conversation_summary": "<brief>",
      "intent": "<intent>",
      "priority": "high|medium|low",
      "reply": "<reply text>",
      "qualification_notes": "<is this a hot lead? what product? what budget signals?>"
    }}
  ],
  "hot_leads": [
    {{
      "username": "<@user>",
      "source": "comment|dm",
      "signal": "<why they're a hot lead>",
      "recommended_action": "<next step>"
    }}
  ],
  "proactive_actions": [
    "<action 1 to drive engagement today>",
    "<action 2>"
  ],
  "summary": {{
    "comments_processed": <n>,
    "dms_processed": <n>,
    "hot_leads_found": <n>,
    "avg_response_time_target": "< 2 hours"
  }}
}}
```"""

        raw = self.call_claude(prompt)
        responses = self.extract_json(raw)
        if not responses:
            responses = {"raw_response": raw}

        hot_leads = len(responses.get("hot_leads", []))
        self.print_result("Hot leads identified", hot_leads)
        return responses

    # ── Tool executors ─────────────────────────────────────────────────────────

    @staticmethod
    def _fetch_pending_comments(_inputs: dict) -> dict:
        return {
            "pending_comments": [
                {"id": "c001", "username": "@sofia_m", "post_id": "p001", "text": "This is absolutely stunning! How much is the rune necklace? 😍", "time": "2h ago", "likes": 3},
                {"id": "c002", "username": "@nordic_liv", "post_id": "p001", "text": "I love Nordic jewellery! Saved this 💛", "time": "3h ago", "likes": 1},
                {"id": "c003", "username": "@james_k", "post_id": "p001", "text": "What silver do you use? Is it recycled?", "time": "4h ago", "likes": 0},
                {"id": "c004", "username": "@emma_gifts", "post_id": "p002", "text": "This would be perfect for my mum's birthday! Tagging @anna_r", "time": "5h ago", "likes": 4},
                {"id": "c005", "username": "@craft_lover", "post_id": "p002", "text": "Do you do custom orders? I want one with my family rune 🙏", "time": "6h ago", "likes": 2},
                {"id": "c006", "username": "@disappointed_user", "post_id": "p001", "text": "I ordered 3 weeks ago and still haven't received anything...", "time": "7h ago", "likes": 0},
            ]
        }

    @staticmethod
    def _fetch_pending_dms(_inputs: dict) -> dict:
        return {
            "pending_dms": [
                {"id": "dm001", "username": "@wedding_planner_uk", "messages": ["Hi! I'm a wedding planner and I'm looking for bridesmaid jewellery for 6 people. Do you do bulk orders?"], "time": "1h ago"},
                {"id": "dm002", "username": "@gift_for_mum", "messages": ["Hey, I saw your rune necklace — what's the price and how long does shipping take to the UK?"], "time": "2h ago"},
                {"id": "dm003", "username": "@viking_fan", "messages": ["I commented CRAFT on your last reel. I'm interested!"], "time": "3h ago"},
            ]
        }

    @staticmethod
    def _classify_intent(inputs: dict) -> dict:
        text = inputs.get("text", "").lower()
        if any(w in text for w in ["price", "cost", "how much", "£", "€", "$", "buy", "order", "purchase"]):
            return {"intent": "buyer", "confidence": "high", "urgency": "immediate"}
        if any(w in text for w in ["custom", "personalise", "my name", "family", "wedding", "bulk"]):
            return {"intent": "enquiry", "confidence": "high", "urgency": "high"}
        if any(w in text for w in ["love", "beautiful", "stunning", "amazing", "gorgeous", "saved"]):
            return {"intent": "compliment", "confidence": "high", "urgency": "medium"}
        if "?" in text:
            return {"intent": "question", "confidence": "medium", "urgency": "medium"}
        if any(w in text for w in ["waiting", "hasn't arrived", "disappointed", "still not", "wrong"]):
            return {"intent": "negative", "confidence": "high", "urgency": "immediate"}
        return {"intent": "general", "confidence": "low", "urgency": "low"}

    # ── Demo output ────────────────────────────────────────────────────────────

    @staticmethod
    def _demo_output(brand: dict) -> dict:
        brand_name = brand.get("name", "us")
        return {
            "processed_at": datetime.now().isoformat(),
            "comment_replies": [
                {
                    "comment_id": "c001",
                    "username": "@sofia_m",
                    "original_comment": "This is absolutely stunning! How much is the rune necklace? 😍",
                    "intent": "buyer",
                    "priority": "high",
                    "reply": f"Thank you Sofia — so glad it caught your eye! 🌿 The Nordic Rune Necklace is €120, handcrafted in sterling silver. We'd love to tell you more about the specific rune meanings too. I've sent you a DM with all the details! ✨",
                    "action": "replied + escalate_to_dm",
                },
                {
                    "comment_id": "c002",
                    "username": "@nordic_liv",
                    "original_comment": "I love Nordic jewellery! Saved this 💛",
                    "intent": "compliment",
                    "priority": "medium",
                    "reply": "That means so much! 🙏 Each piece carries a real piece of Norse history — we hope you find your piece soon. Which rune would be most meaningful to you? 👇",
                    "action": "replied",
                },
                {
                    "comment_id": "c003",
                    "username": "@james_k",
                    "original_comment": "What silver do you use? Is it recycled?",
                    "intent": "question",
                    "priority": "medium",
                    "reply": f"Great question James! We use 925 sterling silver — and yes, 80% is recycled silver sourced from certified ethical suppliers in Scandinavia. Sustainability is core to everything we do at {brand_name}. 🌱 DM us if you'd like more detail on our sourcing!",
                    "action": "replied",
                },
                {
                    "comment_id": "c004",
                    "username": "@emma_gifts",
                    "original_comment": "This would be perfect for my mum's birthday! Tagging @anna_r",
                    "intent": "buyer",
                    "priority": "high",
                    "reply": "What a thoughtful gift — she'll treasure it! 🎁 We offer free gift wrapping and a handwritten card for all orders. I've sent you both a DM with the gift options. She's going to love it! ✨",
                    "action": "replied + escalate_to_dm",
                },
                {
                    "comment_id": "c005",
                    "username": "@craft_lover",
                    "original_comment": "Do you do custom orders? I want one with my family rune 🙏",
                    "intent": "enquiry",
                    "priority": "high",
                    "reply": "Absolutely! Custom pieces are actually our favourite to make — knowing it carries your family's symbol makes the whole process even more meaningful. DM us and we'll discuss your design. We just need a few details to get started! 🔱",
                    "action": "replied + flagged_lead",
                },
                {
                    "comment_id": "c006",
                    "username": "@disappointed_user",
                    "original_comment": "I ordered 3 weeks ago and still haven't received anything...",
                    "intent": "negative",
                    "priority": "high",
                    "reply": "We're really sorry to hear this — that's not the experience we want for you at all. I've sent you a DM right now so we can resolve this immediately. Please check your DMs. 🙏",
                    "action": "replied + escalate_to_dm",
                },
            ],
            "dm_replies": [
                {
                    "dm_id": "dm001",
                    "username": "@wedding_planner_uk",
                    "conversation_summary": "Wedding planner enquiring about bulk bridesmaid jewellery (6 pieces)",
                    "intent": "high_value_enquiry",
                    "priority": "high",
                    "reply": (
                        "Hello! Thank you so much for reaching out — what a beautiful occasion to be involved in! 🌿\n\n"
                        "Yes, we absolutely do wedding and bridesmaid collections. For 6 pieces we offer:\n"
                        "• 10% group discount\n"
                        "• Coordinated designs (matching or complementary)\n"
                        "• Personalised rune for each bridesmaid if desired\n"
                        "• Luxury gift packaging included\n\n"
                        "Could you share the wedding date and the aesthetic/theme you're going for? "
                        "I'd love to suggest some pieces that would work beautifully together!"
                    ),
                    "qualification_notes": "HOT LEAD: Wedding planner = potential repeat buyer + referrals. 6-piece order = €450-600. Priority follow-up.",
                },
                {
                    "dm_id": "dm002",
                    "username": "@gift_for_mum",
                    "conversation_summary": "Asking price and UK shipping time for rune necklace",
                    "intent": "buyer",
                    "priority": "high",
                    "reply": (
                        "Hi! Of course — happy to help 😊\n\n"
                        "Our Norse Rune Necklace is €120 (approx. £103).\n"
                        "UK shipping: 3-5 working days, free on orders over €80.\n\n"
                        "Each piece comes in our signature gift box with a card explaining the rune's meaning — "
                        "makes a beautiful present! 🎁\n\n"
                        "Would you like to know more about which rune might be most meaningful as a gift?"
                    ),
                    "qualification_notes": "Warm lead — gift buyer, UK based. Mention meaning card to add emotional value.",
                },
                {
                    "dm_id": "dm003",
                    "username": "@viking_fan",
                    "conversation_summary": "Responded to CRAFT CTA on reel",
                    "intent": "buyer",
                    "priority": "high",
                    "reply": (
                        "Welcome! 🔱 So glad the reel resonated with you!\n\n"
                        "Here's our full handcrafted collection: [link]\n\n"
                        "Our most loved pieces:\n"
                        "• Nordic Rune Necklace — €120\n"
                        "• Silver Fjord Bracelet — €85\n"
                        "• Viking Knot Ring — €95\n\n"
                        "All made by hand using traditional Nordic techniques. Let me know if you'd like "
                        "more photos or information on any specific piece!"
                    ),
                    "qualification_notes": "Responded to specific CTA — purchase intent is clear. Send catalogue link.",
                },
            ],
            "hot_leads": [
                {
                    "username": "@wedding_planner_uk",
                    "source": "dm",
                    "signal": "Wedding planner seeking 6-piece bridesmaid collection — B2B potential",
                    "recommended_action": "Send custom proposal within 24h. Offer to video call.",
                },
                {
                    "username": "@emma_gifts",
                    "source": "comment",
                    "signal": "Birthday gift buyer — tagging friend = social proof opportunity",
                    "recommended_action": "DM with gift guide + gift wrapping details. Close today.",
                },
                {
                    "username": "@craft_lover",
                    "source": "comment",
                    "signal": "Custom order request — highest margin product type",
                    "recommended_action": "DM with custom order form and 2-3 design options.",
                },
            ],
            "proactive_actions": [
                "Reply to all comments on the reel posted 48h ago before it drops out of algorithm window",
                "Post a Story Poll: 'Which rune meaning resonates most with you?' — generates story replies",
                "Like + save 20 posts from target hashtag (#nordicjewellery) — visibility reciprocity",
                "Leave a thoughtful comment on top 3 competitor posts — gets our name in front of their audience",
            ],
            "summary": {
                "comments_processed": 6,
                "dms_processed": 3,
                "hot_leads_found": 3,
                "avg_response_time_target": "< 2 hours",
            },
        }
