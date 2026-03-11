# AI Social Media Operating System — Platform Overview

## What is it?

The **AI Social Media Operating System (AI-SMOS)** is an autonomous marketing engine that replicates the complete daily workflow of a professional social media manager — but runs automatically, 24/7, with no human input required once configured.

It connects to **Claude claude-opus-4-6** (Anthropic's most capable model) and the **Meta Graph API** to handle the full cycle: researching trends, writing captions, planning reels, replying to comments, scheduling posts, analysing performance, and continuously improving its own strategy.

The system is designed around a simple principle: **everything a social media manager does every day, structured into four daily time blocks, run by specialist AI agents.**

---

## The Four Daily Blocks

```
07:00  🔍 MONITORING BLOCK      Scan trends + review overnight analytics
08:00  💬 ENGAGEMENT BLOCK      Reply to comments and DMs, qualify leads
09:00  ✍️  CONTENT BLOCK         Generate captions, visuals, reel scripts
17:00  📈 GROWTH BLOCK           Schedule posts + extract optimizations
```

Each block is independent. You can run all four together (full cycle) or trigger them individually via CLI or API.

The monthly cycle adds two extra phases run at the start of each month:
- **Strategy** — sets the overarching monthly plan, campaign themes, KPIs
- **Campaign Planning** — breaks strategy into a concrete weekly post calendar

---

## The 10-Agent Pipeline

Each agent is a specialist with its own system prompt, tools, and area of responsibility. They run in sequence, passing their outputs to the next agent as context.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     MONTHLY PLANNING CYCLE                           │
│                                                                       │
│  ┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐  │
│  │   STRATEGY   │────▶│  TREND RESEARCH  │────▶│ CAMPAIGN PLANNER│  │
│  │    AGENT     │     │      AGENT       │     │     AGENT       │  │
│  └──────────────┘     └──────────────────┘     └────────┬────────┘  │
│                                                          │            │
└──────────────────────────────────────────────────────────┼───────────┘
                                                           │
                    ┌──────────────────────────────────────▼
                    │           CONTENT BLOCK (per post)    │
                    │                                        │
                    │  ┌─────────────┐  ┌──────────────┐   │
                    │  │   CONTENT   │  │    VISUAL    │   │
                    │  │    AGENT   │  │     AGENT    │   │
                    │  └─────────────┘  └──────────────┘   │
                    │         │                │            │
                    │         └────────┬───────┘            │
                    │                  ▼                     │
                    │          ┌──────────────┐             │
                    │          │     REEL     │             │
                    │          │    AGENT     │             │
                    │          └──────────────┘             │
                    └──────────────────┬─────────────────────
                                       │
         ┌─────────────────────────────▼─────────────────────────────┐
         │                    DAILY BLOCKS                            │
         │                                                             │
         │  ┌────────────┐  ┌───────────┐  ┌──────────────────────┐  │
         │  │ ENGAGEMENT │  │ SCHEDULER │  │ ANALYTICS+OPTIMIZER  │  │
         │  │   AGENT    │  │   AGENT   │  │       AGENTS         │  │
         │  └────────────┘  └───────────┘  └──────────────────────┘  │
         └─────────────────────────────────────────────────────────────┘
```

### Agent descriptions

---

#### 1. Strategy Agent
**When:** Monthly (or first run)
**Input:** Brand profile + past performance data
**Output:** Monthly content strategy

Performs deep competitive analysis and builds the overarching monthly plan. Uses **Claude's extended thinking** (adaptive reasoning) to weigh market position, past performance, and brand goals.

Produces:
- Monthly campaign themes (4 weeks)
- Content pillar mix (what % of posts per topic)
- Growth strategy (follower tactics, partnership ideas)
- Target KPIs for the month
- Optimal posting frequency

---

#### 2. Trend Research Agent
**When:** Daily (monitoring block) + monthly cycle
**Input:** Brand profile + strategy plan
**Output:** Trend report

Scans the current landscape to surface relevant content opportunities. In live mode it queries trending hashtag APIs, viral reel format databases, and competitor recent posts.

Produces:
- Trending topics with fit scores and urgency ratings
- Trending hashtags grouped by cluster
- Viral reel formats worth replicating
- Trending audio tracks
- Competitor content insights
- Top 3 actionable recommendations

---

#### 3. Campaign Planner Agent
**When:** Weekly (start of each week)
**Input:** Strategy plan + trend report + week number
**Output:** Weekly post calendar

Translates the monthly strategy into a concrete, schedulable post plan for the week. Balances content types against the target mix (reels/carousels/images/stories).

Produces for each post:
- Post type, theme, content pillar
- Hook line, call-to-action
- Hashtag cluster
- Visual notes and shoot direction
- Optimal publish time slot

---

#### 4. Content Agent
**When:** Content block (once per feed post)
**Input:** Post brief + brand profile + strategy
**Output:** Full caption package

Writes production-ready Instagram captions using viral copywriting frameworks (hooks, pattern interrupts, CTAs). Generates multiple caption elements and assembles the final post text.

Produces:
- Hook line (first 1-2 sentences — stops the scroll)
- Body copy with storytelling or education
- Call-to-action
- Full assembled caption
- 30 hashtags grouped by size (niche/mid/broad)
- Carousel slide text (if carousel post)
- Reel script outline

---

#### 5. Visual Agent
**When:** Content block (once per feed post, runs after Content Agent)
**Input:** Post brief + caption package + brand profile
**Output:** Visual production guide

Directs the visual creative without generating actual images — it produces detailed AI image prompts and photography briefs a human or image-generation tool can execute.

Produces:
- Primary image: AI prompt + photography brief
- Carousel slide design specs (colours, layout, text overlay)
- Brand colour palette application
- Typography guidelines
- Production checklist

---

#### 6. Reel Agent
**When:** Content block (only for posts of type `reel`)
**Input:** Post brief + caption package + trend report
**Output:** Full reel production package

Specialises exclusively in short-form video. Skips automatically for non-reel posts. Uses trending formats and audio to maximise watch time and shares.

Produces:
- Reel strategy (format, hook style, pacing)
- Full production script: hook (0-3s) → scenes → closing CTA
- Audio recommendation (trending track or original audio approach)
- Shooting guide (camera angles, B-roll list)
- Editing guide (cuts, effects, text overlays, timings)
- Thumbnail frame description
- Predicted performance metrics

---

#### 7. Engagement Agent
**When:** Daily (engagement block, 08:00)
**Input:** Brand profile
**Output:** Engagement report + reply queue

Processes the inbox — comments and DMs. Classifies each message by intent (buyer, enquiry, compliment, question, negative), writes tailored replies, and flags hot leads for follow-up.

Produces:
- Comment replies with appropriate tone per intent
- DM replies with personalised responses
- Hot lead list (people who asked about buying)
- Proactive engagement suggestions (accounts to engage with)
- Engagement summary stats

---

#### 8. Scheduler Agent
**When:** Growth block (daily, 17:00)
**Input:** Campaign plan + content packages
**Output:** Publishing manifest

Validates each content package is complete, selects the optimal time slot, and queues posts to the Meta Graph API. In demo mode it simulates the publishing queue.

Produces:
- Publishing manifest (post ID, scheduled time, platform status)
- Time slot recommendations based on audience analytics
- Validation checklist per post

---

#### 9. Analytics Agent
**When:** Daily (monitoring block, 07:00) + growth block
**Input:** Brand profile + published posts
**Output:** Performance report

Pulls data from the Instagram Insights API and calculates key metrics. Identifies what worked, what didn't, and surfaces patterns.

Produces:
- Account metrics (followers, reach, impressions, growth)
- Per-post performance (engagement rate, saves, shares)
- Content type breakdown (reels vs carousels vs images)
- DM funnel stats (enquiries → leads → sales)
- Hashtag performance
- KPI scorecard vs monthly targets
- Key insights (plain English takeaways)

---

#### 10. Optimization Agent
**When:** Growth block (runs after Analytics Agent)
**Input:** Analytics report + strategy plan + campaign plan
**Output:** Optimization recommendations

The system's self-improvement engine. Uses **Claude's extended thinking** to deeply analyse performance data and generate prioritised recommendations. Its output feeds back into the next Strategy cycle.

Produces:
- Key learnings from the week
- Content mix adjustments (should reels go from 40% to 50%?)
- Quick wins (actions to take this week)
- Strategic shifts (longer-term direction changes)
- A/B tests to run next week
- Next week's priority list
- Updated KPI targets

---

## How Agents Share Context

Agents don't talk to each other directly. Instead, the **Orchestrator** passes the output of each agent as input to the next:

```
Strategy output  →  passed to  →  Trend Research (strategy_plan)
Trend output     →  passed to  →  Campaign Planner (trend_report)
Campaign output  →  passed to  →  Content Agent (post_brief per post)
Content output   →  passed to  →  Visual Agent (content_package)
Content output   →  passed to  →  Reel Agent (content_package)
Analytics output →  passed to  →  Optimization Agent (analytics_report)
Strategy output  →  passed to  →  Optimization Agent (strategy_plan)
```

All outputs are also saved to disk (`storage/db/<brand>/`). When running individual blocks, agents load the most recent saved output from prior runs rather than re-running upstream agents. This means:

- The **monitoring block** loads the stored strategy to give trend research the right context.
- The **content block** loads the stored strategy + trends + campaign so it can pick up mid-week.
- The **growth block** loads the stored campaign and analytics to generate optimizations.

---

## Agent Architecture — Technical

Every agent inherits from `BaseAgent` and follows the same pattern:

```
BaseAgent
├── get_system_prompt()   →  Defines the agent's persona and task
├── get_tools()           →  List of AgentTool objects (schema + Python callable)
├── run(inputs)           →  Entry point — builds prompt, calls Claude, returns dict
└── call_claude(message)  →  Agentic loop: stream → detect tool calls → execute → loop
```

### The Agentic Loop

When an agent calls `call_claude()`:

1. The user message is sent to Claude claude-opus-4-6 with the agent's system prompt and registered tools.
2. Claude's response streams token by token to the terminal.
3. If Claude calls a tool (e.g. `fetch_trending_hashtags`), the loop pauses, executes the Python function, and feeds the result back to Claude.
4. Claude continues reasoning with the tool result and may call more tools.
5. When Claude stops (stop reason `end_turn`), the accumulated text is returned.
6. The `run()` method extracts the JSON from the text and returns it as a Python dict.

### Tool System

Each agent registers tools using `AgentTool`:

```python
AgentTool(
    name="fetch_trending_hashtags",
    description="Fetch currently trending hashtags for a given niche",
    input_schema={"type": "object", "properties": {"niche": {"type": "string"}}},
    executor=lambda inputs: {"hashtags": ["#jewellery", "#handmade", ...]}
)
```

In demo mode, executors return mock data. In live mode, they call real APIs (RapidAPI, Meta Graph API, etc.).

### Models Used

| Agent | Model | Extended Thinking |
|---|---|---|
| Strategy Agent | claude-opus-4-6 | Yes (adaptive) |
| Optimization Agent | claude-opus-4-6 | Yes (adaptive) |
| All other agents | claude-opus-4-6 | No |

---

## Web Dashboard

The web interface (`/`) provides a visual alternative to the CLI.

### Sections

**Run Cycle**
- Select brand, cycle type (full / monitoring / engagement / content / growth), and week number
- Click Run — a background job starts immediately
- Live logs stream to the terminal panel via Server-Sent Events
- Stats cards update when the cycle completes (followers, engagement, leads, posts)

**Results**
- Browse stored outputs per section: Strategy, Trends, Campaign, Analytics, Optimization
- Formatted tables for each data type

**Automation**
- Set custom times for each daily block
- Enable/disable the daily scheduler (powered by APScheduler)
- View next scheduled run times per block

**Brands**
- See all available brand profiles (built-in + uploaded)
- Upload a new brand profile by pasting JSON or dragging a `.json` file

---

## Daily Automation

When automation is enabled via the web UI or API, the system runs four jobs every day:

| Time (configurable) | Block | Agents |
|---|---|---|
| 07:00 | Monitoring | Trend Research + Analytics |
| 08:00 | Engagement | Engagement Agent |
| 09:00 | Content | Content + Visual + Reel |
| 17:00 | Growth | Scheduler + Optimization |

The scheduler uses APScheduler with a `BackgroundScheduler` running in the same process as the web server. Week number is computed automatically from the current day of the month.

---

## Typical Weekly Output (Demo Mode)

Running a full cycle produces:

| Output | Volume |
|---|---|
| Campaign themes | 4 (one per week) |
| Posts planned | 6 per week |
| Content packages | 4 feed posts (stories are brief) |
| Reel packages | 2 (full production scripts) |
| Comment replies | 6 |
| DM replies | 3 |
| Hot leads flagged | 3 |
| Proactive engagement actions | 4 |
| Posts scheduled | 6 |
| Key insights | 5 |
| Optimization quick wins | 3 |
| A/B tests suggested | 3 |

---

## Customising the System

### Add a new agent

1. Create `agents/my_agent.py` inheriting from `BaseAgent`.
2. Implement `get_system_prompt()`, `get_tools()`, and `run()`.
3. Import and instantiate it in `orchestrator/orchestrator.py`.
4. Call it at the right point in the pipeline.

### Change the content mix

Edit `DEFAULT_CONTENT_MIX` in `config/settings.py`:

```python
DEFAULT_CONTENT_MIX = {
    "reels": 0.50,      # increase reels
    "carousels": 0.25,
    "images": 0.15,
    "stories": 0.10,
}
```

### Change posting times

Edit `OPTIMAL_POSTING_TIMES` in `config/settings.py` or override via your brand profile's `social_media.instagram.best_posting_times` field.

### Use a different Claude model

Change `DEFAULT_MODEL` or `FAST_MODEL` in `config/settings.py`:

```python
DEFAULT_MODEL = "claude-opus-4-6"   # most capable
FAST_MODEL = "claude-haiku-4-5"     # fastest + cheapest
```
