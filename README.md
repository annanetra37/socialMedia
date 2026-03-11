# AI Social Media Operating System — README

A fully automated social media marketing system powered by **Claude claude-opus-4-6**. It runs a 10-agent pipeline that handles strategy, content creation, engagement, scheduling, analytics, and optimization — all from a single command or a web dashboard.

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Environment Variables](#environment-variables)
5. [Run Modes](#run-modes)
6. [Running Locally — CLI](#running-locally--cli)
7. [Running Locally — Web Server](#running-locally--web-server)
8. [Brand Profiles](#brand-profiles)
9. [Deploying to Railway](#deploying-to-railway)
10. [Storage & Persistence](#storage--persistence)

---

## Project Structure

```
socialMedia/
├── main.py                          # CLI entry point
├── requirements.txt
├── Procfile                         # Railway startup command
├── railway.toml                     # Railway service config
├── nixpacks.toml                    # Railway build config
├── .env.example                     # Environment variable template
│
├── config/
│   ├── settings.py                  # Global settings (loaded from .env)
│   └── brand_profiles/
│       └── example_brand.json       # Example: "Luna Silver" jewellery brand
│
├── agents/                          # 10 specialist AI agents
│   ├── base_agent.py                # Abstract base class + AgentTool
│   ├── strategy_agent.py
│   ├── trend_research_agent.py
│   ├── campaign_planner_agent.py
│   ├── content_agent.py
│   ├── visual_agent.py
│   ├── reel_agent.py
│   ├── engagement_agent.py
│   ├── scheduler_agent.py
│   ├── analytics_agent.py
│   └── optimization_agent.py
│
├── orchestrator/
│   └── orchestrator.py              # Runs agents in sequence (the conductor)
│
├── api/                             # Web server (Railway / web UI)
│   ├── app.py                       # FastAPI application + REST API
│   ├── scheduler.py                 # APScheduler-based daily automation
│   └── templates/
│       └── index.html               # Single-page web dashboard
│
├── dashboard/
│   └── cli_dashboard.py             # Rich-powered terminal UI
│
├── tools/
│   ├── instagram_api.py             # Meta Graph API wrapper
│   └── analytics_tools.py           # Analytics calculation helpers
│
└── storage/
    ├── data_store.py                # JSON-file persistence layer
    └── db/                          # Auto-created at runtime
        └── <brand_slug>/            # One directory per brand
            ├── strategy/
            ├── trends/
            ├── campaigns/
            ├── content/
            ├── visuals/
            ├── reels/
            ├── engagement/
            ├── schedules/
            ├── analytics/
            └── optimizations/
```

---

## Requirements

- **Python 3.11+** (3.12 recommended)
- All dependencies are in `requirements.txt`:

```
anthropic>=0.40.0        # Claude API SDK
python-dotenv>=1.0.0     # .env loading
rich>=13.7.0             # Terminal UI
schedule>=1.2.0          # Simple task scheduling
requests>=2.31.0         # HTTP calls (Meta API)
aiohttp>=3.9.0           # Async HTTP
Pillow>=10.0.0           # Image handling
pytz>=2024.1             # Timezone support
tabulate>=0.9.0          # Table formatting
fastapi>=0.115.0         # Web server framework
uvicorn[standard]>=0.32.0 # ASGI server
apscheduler>=3.10.0      # Daily automation scheduler
jinja2>=3.1.0            # HTML templating
aiofiles>=23.0.0         # Async file serving
```

---

## Installation

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd socialMedia

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy the environment template
cp .env.example .env

# 5. Edit .env with your API keys (see next section)
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values.

### Required for live mode

| Variable | Description | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API key | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| `RUN_MODE` | `demo` or `live` | Set to `demo` to test without any API keys |

### Required for Instagram publishing (live mode only)

| Variable | Description | Where to get it |
|---|---|---|
| `META_ACCESS_TOKEN` | Long-lived Meta user access token | Meta for Developers → Tools → Graph API Explorer → generate token with `instagram_basic`, `instagram_content_publish`, `pages_read_engagement` permissions, then extend it |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | Your Instagram Business Account ID | Graph API Explorer: `GET /me/accounts`, find your page, then `GET /{page-id}?fields=instagram_business_account` |
| `META_APP_ID` | Your Meta App ID | Meta for Developers → Your App → App Settings → Basic |
| `META_APP_SECRET` | Your Meta App Secret | Same location as App ID |

### Optional — Image generation

| Variable | Description | Where to get it |
|---|---|---|
| `OPENAI_API_KEY` | For DALL-E image generation | [platform.openai.com](https://platform.openai.com) → API Keys |
| `STABILITY_API_KEY` | For Stable Diffusion images | [platform.stability.ai](https://platform.stability.ai) |

### Optional — Trend data

| Variable | Description | Where to get it |
|---|---|---|
| `RAPIDAPI_KEY` | For trending hashtag and audio APIs | [rapidapi.com](https://rapidapi.com) → Subscribe to social media trend APIs |

### Optional — App behaviour

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `TIMEZONE` | `UTC` | IANA timezone string e.g. `Europe/London`, `America/New_York` |

### Getting your Meta/Instagram credentials — step by step

1. Go to [developers.facebook.com](https://developers.facebook.com) and create an app (type: **Business**).
2. Add the **Instagram Graph API** product to your app.
3. Connect your Instagram Business Account to a Facebook Page.
4. In Graph API Explorer, select your app and generate a token with these permissions:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`
   - `instagram_manage_comments`
   - `instagram_manage_insights`
5. Exchange for a long-lived token (valid 60 days):
   ```
   GET https://graph.facebook.com/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id={app-id}
     &client_secret={app-secret}
     &fb_exchange_token={short-lived-token}
   ```
6. Get your Instagram Business Account ID:
   ```
   GET https://graph.facebook.com/me/accounts
   # Find your page ID, then:
   GET https://graph.facebook.com/{page-id}?fields=instagram_business_account
   ```

---

## Run Modes

The system has two modes controlled by the `RUN_MODE` environment variable:

| Mode | Claude API | Meta API | Cost | Use for |
|---|---|---|---|---|
| `demo` | No calls made | No calls made | Free | Testing, development, demos |
| `live` | Real Claude claude-opus-4-6 | Real Instagram API | Paid | Production use |

In demo mode every agent returns realistic pre-built mock data — the full pipeline runs, all JSON files are saved, and the dashboard displays everything correctly. No API keys are needed.

---

## Running Locally — CLI

```bash
# Demo mode — full cycle with example brand (Luna Silver)
RUN_MODE=demo python main.py

# Full cycle — week 1
python main.py --cycle full --week 1

# Run a specific block only
python main.py --cycle monitoring     # Block A: trends + analytics
python main.py --cycle engagement     # Block B: comments + DMs
python main.py --cycle content        # Block C: content creation
python main.py --cycle growth         # Block D: scheduling + optimization

# Run week 2 content
python main.py --cycle content --week 2

# Use your own brand profile
python main.py --brand path/to/my_brand.json

# Show results from the last run (no re-run)
python main.py --show results

# Show the agent pipeline diagram
python main.py --pipeline
```

### What you'll see

The terminal renders a live Rich dashboard:
- Coloured agent panels as each agent activates
- Streaming Claude output token by token (in live mode)
- Tool call / result previews
- A summary table at the end with key metrics

---

## Running Locally — Web Server

The web server gives you a browser-based dashboard with live log streaming.

```bash
# Start in demo mode
RUN_MODE=demo uvicorn api.app:app --reload --port 8000

# Start in live mode
RUN_MODE=live uvicorn api.app:app --reload --port 8000
```

Open `http://localhost:8000` in your browser.

### API endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web dashboard UI |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/brands` | List all brand profiles |
| `POST` | `/api/brands` | Upload a new brand JSON |
| `POST` | `/api/cycle/run` | Start a cycle (returns `job_id`) |
| `GET` | `/api/cycle/status/{job_id}` | Poll job status |
| `GET` | `/api/stream/{job_id}` | Server-Sent Events live log stream |
| `GET` | `/api/results/{brand_slug}` | All stored results for a brand |
| `GET` | `/api/results/{brand_slug}/{section}` | Single section of results |
| `GET` | `/api/schedule` | Automation schedule status |
| `POST` | `/api/schedule/enable` | Enable daily automation |
| `POST` | `/api/schedule/disable` | Disable daily automation |

---

## Brand Profiles

A brand profile is a JSON file that tells every agent about your brand. Place it anywhere and pass the path with `--brand`, or upload it via the web UI.

### Required fields

```json
{
  "name": "Your Brand Name",
  "industry": "e.g. Fashion / E-commerce",
  "brand_voice": "Describe tone, style, values",
  "target_audience": {
    "age_range": "25-40",
    "gender": "primarily female",
    "location": "UK, USA",
    "interests": ["fashion", "sustainability"]
  },
  "products": [
    { "name": "Product Name", "price_eur": 99, "bestseller": true }
  ],
  "content_pillars": {
    "product_showcase": 0.40,
    "behind_the_scenes": 0.30,
    "lifestyle": 0.30
  },
  "social_media": {
    "instagram": {
      "handle": "@yourhandle",
      "current_followers": 5000,
      "avg_engagement_rate": 3.5
    }
  },
  "goals": {
    "monthly_follower_growth": 500,
    "engagement_rate_target": 5.0
  }
}
```

See `config/brand_profiles/example_brand.json` for a complete example.

---

## Deploying to Railway

1. Push your code to GitHub.
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub.
3. Select your repository.
4. Railway auto-detects `Procfile` and `railway.toml`.
5. Add environment variables in Railway → your service → **Variables**:
   - `RUN_MODE=live`
   - `ANTHROPIC_API_KEY=sk-ant-...`
   - `META_ACCESS_TOKEN=...` (optional)
   - `INSTAGRAM_BUSINESS_ACCOUNT_ID=...` (optional)
6. Deploy. Your app will be live at `https://<your-app>.railway.app`.

The `Procfile` tells Railway to run:
```
uvicorn api.app:app --host 0.0.0.0 --port $PORT
```

Railway automatically sets the `$PORT` variable.

---

## Storage & Persistence

All outputs are saved as timestamped JSON files under `storage/db/<brand_slug>/`.

```
storage/db/luna_silver/
├── strategy/     2024-01-15_strategy.json
├── trends/       2024-01-15_trends.json
├── campaigns/    2024-01-15_week1_campaign.json
├── content/      post_001_content.json
├── visuals/      post_001_visual.json
├── reels/        post_001_reel.json
├── engagement/   2024-01-15_engagement.json
├── schedules/    2024-01-15_week1_schedule.json
├── analytics/    2024-01-15_analytics.json
└── optimizations/ 2024-01-15_optimization.json
```

Files are never overwritten — each run appends new timestamped files. The system always loads the most recent file per category when it needs to reference prior context.

> **Railway note:** Railway's filesystem is ephemeral. On every redeploy, `storage/db/` is wiped. For persistent storage on Railway, mount a volume via Railway → your service → **Volumes** and set the mount path to `/app/storage/db`.
