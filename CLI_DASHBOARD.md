# CLI Dashboard — User Guide

The CLI dashboard is the terminal interface for the AI Social Media Operating System. It renders live agent output, coloured summary tables, and stored data — all directly in your terminal using the **Rich** library.

---

## Quick Start

```bash
# Run the full cycle in demo mode (no API keys needed)
RUN_MODE=demo python main.py

# Run in live mode (real Claude API calls)
RUN_MODE=live python main.py
```

When you run any command, the dashboard automatically:
1. Clears the terminal and shows the welcome screen
2. Displays the agent pipeline diagram
3. Runs the requested cycle — printing each agent's output live
4. Shows a summary table when complete

---

## All Commands

```
python main.py [--cycle BLOCK] [--week N] [--brand FILE] [--show results] [--pipeline]
```

### `--cycle` — choose what to run

| Command | What it does |
|---|---|
| `python main.py` | Full cycle — all 8 phases in sequence (default) |
| `python main.py --cycle full` | Same as above, explicit |
| `python main.py --cycle monitoring` | Block A — trends + analytics only |
| `python main.py --cycle engagement` | Block B — comments + DMs only |
| `python main.py --cycle content` | Block C — content creation only |
| `python main.py --cycle growth` | Block D — scheduling + optimization only |

### `--week` — set the week number

```bash
python main.py --cycle full --week 2
python main.py --cycle content --week 3
```

Valid values: `1`, `2`, `3`, `4` (default is `1`). The week number tells the Campaign Planner which week of the monthly strategy to build content for.

### `--brand` — use your own brand profile

```bash
python main.py --brand /path/to/my_brand.json
python main.py --cycle content --brand brands/coffee_shop.json
```

Without `--brand`, the system uses the built-in example brand (`config/brand_profiles/example_brand.json` — "Luna Silver" jewellery).

### `--show results` — browse stored data without re-running

```bash
python main.py --show results
python main.py --show results --brand my_brand.json
```

Opens the results viewer for the last run. Shows all stored outputs (strategy, trends, campaign, analytics, optimizations) plus the data store file browser. Nothing is re-run — it reads from saved JSON files.

### `--pipeline` — show the agent diagram

```bash
python main.py --pipeline
```

Prints the 10-agent pipeline diagram and exits immediately. Useful to quickly understand the system structure.

---

## What You See When It Runs

### 1. Welcome Screen

The first thing shown on every run:

```
  ╔═══════════════════════════════════════════════════════════════╗
  ║          AI SOCIAL MEDIA OPERATING SYSTEM                     ║
  ║          Powered by Claude claude-opus-4-6                         ║
  ╚═══════════════════════════════════════════════════════════════╝

  ┌──────────────────────┐
  │  Brand:   Luna Silver │
  │  Mode:    DEMO        │
  │  Started: Monday...   │
  └──────────────────────┘
```

- **Brand** — the name loaded from your brand profile
- **Mode** — `DEMO` (yellow) or `LIVE` (green)
- **Started** — current date and time

### 2. Agent Pipeline Diagram

Shown immediately after the welcome screen on every run:

```
  ┌────────────────────────────────────────────────────────────┐
  │  1. Strategy Agent      ──►  Monthly strategy + pillars    │
  │  2. Trend Research      ──►  Viral formats + hashtags      │
  │  3. Campaign Planner    ──►  Weekly posting calendar       │
  │  4. Content Agent       ──►  Captions + hashtags + CTAs    │
  │  5. Visual Agent        ──►  Image prompts + design specs  │
  │  6. Reel Agent          ──►  Video scripts + shot list     │
  │  7. Engagement Agent    ──►  Comment/DM replies + leads    │
  │  8. Scheduler Agent     ──►  Publishing via Instagram API  │
  │  9. Analytics Agent     ──►  Performance metrics           │
  │ 10. Optimization Agent  ──►  Improvements → back to #1     │
  └────────────────────────────────────────────────────────────┘
```

### 3. Phase Headers

Each phase is announced with a horizontal rule:

```
────────────── 📋 STRATEGY  Monthly strategy generation ──────────────
```

In **live mode**, you also see each agent's Claude output streaming live, token by token, in the agent's panel colour. Tool calls are shown as they happen:

```
  ⚙  Calling tool  analyse_competitor
     input: {"competitor": "rival_jewellery"}

  ✓  analyse_competitor result:  {"strengths": [...], "weaknesses": [...]}
```

In **demo mode**, agents return pre-built mock data instantly — no streaming.

After each phase:
```
  ✓ Completed in 2.4s
```

---

## The Summary Panels

After each phase completes, the dashboard prints a formatted summary. Here is what each one looks like and what to read from it.

---

### Strategy Summary

Shown after the Strategy Agent runs.

**Content Pillars table**
```
╭─────────────────────────────────────────────────────────╮
│                     Content Pillars                      │
├─────────────────────┬───────┬──────────────────────────┤
│ Pillar              │ Mix % │ Rationale                │
├─────────────────────┼───────┼──────────────────────────┤
│ Product Showcase    │  40%  │ Drive direct sales       │
│ Behind the Scenes   │  30%  │ Build trust              │
│ Lifestyle           │  30%  │ Aspirational content     │
╰─────────────────────┴───────┴──────────────────────────╯
```

**Weekly Campaign Themes table**
```
╭─────────────────────────────────────────────────────────╮
│                Weekly Campaign Themes                    │
├──────┬──────────────────┬────────────┬──────────────────┤
│ Week │ Theme            │ Emotion    │ Hook Style       │
├──────┼──────────────────┼────────────┼──────────────────┤
│  1   │ New Beginnings   │ hope       │ question         │
│  2   │ Craftsmanship    │ pride      │ bold statement   │
│  3   │ Customer Stories │ belonging  │ social proof     │
│  4   │ Monthly Review   │ gratitude  │ milestone        │
╰──────┴──────────────────┴────────────┴──────────────────╯
```

**KPIs panel**
```
╭──────────────────────────────────────────────────────────╮
│  KPIs                                                     │
│  Followers target: +500/month  |  Engagement target: 5%  │
│  DM leads target: 20                                      │
╰──────────────────────────────────────────────────────────╯
```

---

### Trend Report

Shown after the Trend Research Agent runs.

**Trending Topics table**
```
╭────────────────────────────────────────────────────────────────────────╮
│                          Trending Topics                                │
├──────────────────────┬──────────────┬──────┬──────────┬───────────────┤
│ Topic                │ Platform     │ Fit  │ Urgency  │ Angle         │
├──────────────────────┼──────────────┼──────┼──────────┼───────────────┤
│ Slow fashion revival │ Instagram    │ 9/10 │ high     │ Behind the... │
│ Valentine's gifting  │ Instagram    │ 8/10 │ urgent   │ Perfect gi... │
╰──────────────────────┴──────────────┴──────┴──────────┴───────────────╯
```

- **Fit** — how relevant the trend is to your brand (out of 10)
- **Urgency** — `urgent` (act now), `high`, `medium`, `low`

**Top Recommendations panel** — 3 bullet points of what to do with the trends this week.

---

### Week's Posting Calendar

Shown after the Campaign Planner runs.

```
╭──────────────────────────────────────────────────────────────────────────╮
│             Week 1 — New Beginnings & Fresh Starts                       │
├─────────┬───────┬──────────┬──────────┬─────────────────────┬───────────┤
│ Day     │ Time  │ Type     │ Priority │ Hook                │ CTA       │
├─────────┼───────┼──────────┼──────────┼─────────────────────┼───────────┤
│ Monday  │ 12:00 │ REEL     │ 🔴       │ 3 signs your jew…   │ Shop now  │
│ Tuesday │ 18:00 │ CAROUSEL │ 🟡       │ Our making-of pr…   │ Save this │
│ Thursday│ 11:00 │ IMAGE    │ 🟢       │ Nordic winter mor…  │ Tag a fri │
│ Friday  │ 19:00 │ REEL     │ 🔴       │ POV: you finally…   │ Link in b │
│ Saturday│ 10:00 │ STORY    │ 🟡       │ Behind the scene…   │ Swipe up  │
│ Sunday  │ 11:00 │ STORY    │ 🟢       │ Week recap          │ —         │
╰─────────┴───────┴──────────┴──────────┴─────────────────────┴───────────╯
  Total: 6 posts  (2 reels  2 carousels  1 images  1 stories)
```

**Post type colours:**
- `REEL` — red
- `CAROUSEL` — blue
- `IMAGE` — green
- `STORY` — magenta

**Priority icons:**
- 🔴 High — must publish, high reach potential
- 🟡 Medium — standard post
- 🟢 Low — filler / story

---

### Content Package

One panel per feed post (stories are skipped). Shown for each post after the Content Agent runs.

```
╭─────────────────────────────────────────────────────╮
│  Post: post_001  |  Type: REEL                       │
╰─────────────────────────────────────────────────────╯

╭──────── Caption ────────────────────────────────────╮
│  Hook: 3 signs your jewellery is telling the wrong  │
│  story about you…                                    │
│                                                      │
│  [body copy]                                         │
│                                                      │
│  CTA: Save this for your next jewellery shopping    │
│  trip. Link in bio.                                  │
╰─────────────────────────────────────────────────────╯

  #jewellery #handmadejewellery #slowfashion ...
```

The full hashtag set (30 tags) is shown in dim text below the caption panel.

---

### Engagement Report

Shown after the Engagement Agent runs.

**Hot Leads table** — people who signalled buying intent in comments or DMs:
```
╭─────────────────────────────────────────────────────────────────────╮
│                          🔥 Hot Leads                                │
├──────────────┬──────────┬──────────────────────────┬───────────────┤
│ Username     │ Source   │ Signal                   │ Next Action   │
├──────────────┼──────────┼──────────────────────────┼───────────────┤
│ @sarah_m     │ DM       │ "How much is the ring?" │ Send price DM │
│ @nordic_life │ Comment  │ "I need this in my life" │ Reply w/ link │
╰──────────────┴──────────┴──────────────────────────┴───────────────╯
  Comments processed: 6  |  DMs processed: 3  |  Hot leads: 3
```

**Proactive Growth Actions panel** — suggested accounts to engage with and why:
```
╭─── Proactive Growth Actions ────────────────────────────────────────╮
│  • Comment on @thenordicstylist's latest post                       │
│  • Like 10 posts from #slowfashion hashtag                          │
│  • Follow 5 accounts from competitor's followers list               │
│  • Reply to story mentions within 2 hours                           │
╰─────────────────────────────────────────────────────────────────────╯
```

---

### Publishing Schedule

Shown after the Scheduler Agent runs.

```
╭────────────────────────────────────────────────────────────────────────╮
│                          Publishing Queue                               │
├──────────┬──────────┬──────────────────┬──────────┬────────────┬───────┤
│ Post ID  │ Day      │ Scheduled (UTC)  │ Type     │ Status     │ Prev… │
├──────────┼──────────┼──────────────────┼──────────┼────────────┼───────┤
│ post_001 │ Monday   │ 2024-01-15 12:00 │ REEL     │ scheduled  │ 3 si… │
│ post_002 │ Tuesday  │ 2024-01-16 18:00 │ CAROUSEL │ scheduled  │ Our … │
│ post_003 │ Thursday │ 2024-01-18 11:00 │ IMAGE    │ scheduled  │ Nord… │
╰──────────┴──────────┴──────────────────┴──────────┴────────────┴───────╯
  Total: 6 posts  |  Feed: 4  |  Stories: 2
```

**Status colours:**
- `published` — green (already live)
- `scheduled` — yellow (queued, not yet published)
- `draft` — dim (content ready, not yet submitted to API)

---

### Analytics Dashboard

Shown after the Analytics Agent runs.

**Account Metrics panel:**
```
╭─── Account Metrics ─────────────────────────────────────╮
│  Followers gained:  +127  (+2.5%)                        │
│  Total reach:       18,420                               │
│  Profile visits:    892                                  │
│  Website clicks:    134                                  │
╰─────────────────────────────────────────────────────────╯
```

**Content Type Performance table:**
```
╭──────────────────────────────────────────────────────────╮
│              Content Type Performance                     │
├──────────┬───────┬────────────────┬────────────────────  │
│ Type     │ Posts │ Avg Engagement │ Avg Reach            │
├──────────┼───────┼────────────────┼──────────────────── │
│ REELS    │ 2     │ 6.8%           │ 4,200                │
│ CAROUSELS│ 2     │ 4.2%           │ 2,100                │
│ IMAGES   │ 1     │ 3.1%           │ 1,800                │
│ STORIES  │ 2     │ —              │ 1,200                │
╰──────────┴───────┴────────────────┴────────────────────╯
```

**Key Insights panel** — 5 plain-English takeaways:
```
╭─── Key Insights ────────────────────────────────────────╮
│  💡 Reels with "POV" hooks outperformed by 2x           │
│  💡 Thursday 11am posts consistently reach more people  │
│  💡 Posts with price tags get 40% more DMs              │
│  💡 Hashtag cluster #slowfashion drove most saves       │
│  💡 Story polls doubled profile visits                  │
╰─────────────────────────────────────────────────────────╯
```

---

### Optimization Recommendations

Shown after the Optimization Agent runs. This is the self-improvement output that feeds back into next week's strategy.

**Performance verdict** — displayed at the top in colour:
- `EXCELLENT` — green
- `GOOD` — cyan
- `AVERAGE` — yellow
- `POOR` — red

**Quick Wins table:**
```
╭────────────────────────────────────────────────────────────────────────╮
│                              Quick Wins                                 │
├──────────────────────────────────┬──────────────────┬────────┬─────── │
│ Action                           │ Impact           │ Effort │ When   │
├──────────────────────────────────┼──────────────────┼────────┼─────── │
│ Add price to every product post  │ +30% DM enquiries│ LOW    │ week   │
│ Post reels before 12pm           │ +20% reach       │ LOW    │ immed  │
│ Pin best-performing reel         │ Ongoing traffic  │ LOW    │ today  │
╰──────────────────────────────────┴──────────────────┴────────┴───────╯
```

**Content Mix Update panel** — shows current vs recommended split:
```
╭─── Content Mix Update ──────────────────────────────────╮
│  reels:     40% → 50%                                    │
│  carousels: 30% → 25%                                    │
│  images:    20% → 15%                                    │
│  stories:   10% → 10%                                    │
╰─────────────────────────────────────────────────────────╯
```

**Next Week's Priorities panel:**
```
╭─── Next Week's Priorities ──────────────────────────────╮
│  1. Increase reel frequency to 3 per week               │
│  2. Test price-anchoring captions on product posts      │
│  3. Run a giveaway to boost story engagement            │
╰─────────────────────────────────────────────────────────╯
```

---

### End-of-Cycle Summary Table

After a full cycle completes, a final table summarises all 8 phases:

```
━━━━━━━━━━━━━━━━━━━━ ✅  CYCLE COMPLETE ━━━━━━━━━━━━━━━━━━━━

╭──────────────────────────────────────────────────────╮
│             Weekly Summary — Luna Silver              │
├──────────────┬──────────────────────────────┬────────┤
│ Phase        │ Output                       │ Status │
├──────────────┼──────────────────────────────┼────────┤
│ Strategy     │ 4 campaign themes            │ ✅     │
│ Trends       │ 6 topics found               │ ✅     │
│ Campaign     │ 6 posts planned              │ ✅     │
│ Content      │ 4 packages generated         │ ✅     │
│ Engagement   │ 3 hot leads                  │ ✅     │
│ Schedule     │ 6 posts queued               │ ✅     │
│ Analytics    │ Engagement: 4.8%             │ ✅     │
│ Optimization │ 3 quick wins                 │ ✅     │
╰──────────────┴──────────────────────────────┴────────╯

╭─── Key Metrics ─────────────────────────────────────╮
│  Followers gained this week:  +127                   │
│  Hot leads identified:        3                      │
│  Next week's #1 priority:     Increase reel freq...  │
╰─────────────────────────────────────────────────────╯
```

---

### Stored Data Browser

Shown at the end of `--show results` runs:

```
━━━━━━━━━━━━━━━━━━━━ 📁 Stored Data Browser ━━━━━━━━━━━━━━━

╭─────────────────────────────────────────────────────────────╮
│                    Data Store Contents                       │
├──────────────────┬───────┬──────────────────────────────────┤
│ Category         │ Files │ Latest File                      │
├──────────────────┼───────┼──────────────────────────────────┤
│ strategy         │ 3     │ 2024-01-15_strategy.json         │
│ trends           │ 7     │ 2024-01-15_trends.json           │
│ campaigns        │ 4     │ 2024-01-15_week1_campaign.json   │
│ content          │ 12    │ post_004_content.json            │
│ analytics        │ 7     │ 2024-01-15_analytics.json        │
│ optimizations    │ 7     │ 2024-01-15_optimization.json     │
╰──────────────────┴───────┴──────────────────────────────────╯
```

Shows how many JSON files are stored per category and which is the most recent. All files are in `storage/db/<brand_slug>/`.

---

## Colour Key

| Colour | Meaning |
|---|---|
| Blue | Titles, headers, strategy output |
| Cyan | Trend data, analytics, general info |
| Green | Positive values, engagement stats, completed |
| Yellow | Demo mode warning, campaign calendar, hooks |
| Red | Reels, high priority, poor performance |
| Magenta | Trend topics, stories, analytics headers |
| Dim/Grey | Captions, metadata, file names |
| Bold White | Phase headers, key numbers |

---

## Tips

**Run demo mode first** — always test with `RUN_MODE=demo` before connecting real APIs. The full pipeline runs in seconds with no cost.

**Use `--show results` to re-read outputs** — if you want to review last run's data without triggering agents again, this is much faster than re-running.

**Run individual blocks during the day** — instead of the full cycle every time, run the block you actually need:
```bash
# Morning — check what's trending
python main.py --cycle monitoring

# Mid-morning — process overnight DMs
python main.py --cycle engagement

# When you need content for the week
python main.py --cycle content --week 2

# End of day — schedule and review
python main.py --cycle growth
```

**Check the pipeline diagram any time**:
```bash
python main.py --pipeline
```

**Pipe output to a file** if you want to save the terminal session:
```bash
python main.py 2>&1 | tee run_log.txt
```

**Terminal width matters** — tables are best displayed in a terminal at least 120 characters wide. Most modern terminals support this; you can usually set it in your terminal's preferences.
