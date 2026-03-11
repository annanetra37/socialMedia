"""
FastAPI web server for the AI Social Media Operating System.

Endpoints:
  GET  /                        → Web dashboard UI
  GET  /api/health              → Health check
  GET  /api/brands              → List available brand profiles
  POST /api/brands              → Upload a new brand profile JSON
  POST /api/cycle/run           → Start a cycle (background job)
  GET  /api/cycle/status/{id}   → Poll job status + streaming log
  GET  /api/results/{brand}     → Full results for a brand
  GET  /api/results/{brand}/{section}  → strategy|trends|campaign|analytics|optimizations
  GET  /api/schedule            → Current automation schedule
  POST /api/schedule/enable     → Enable daily automation
  POST /api/schedule/disable    → Disable daily automation
  GET  /api/stream/{job_id}     → Server-Sent Events live log stream
"""

import json
import sys
import threading
import time
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from api.scheduler import DailyScheduler
from config.settings import RUN_MODE, BRAND_PROFILES_DIR, STORAGE_DIR
from storage.data_store import DataStore

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Social Media OS",
    description="Fully automated social media marketing — powered by Claude claude-opus-4-6",
    version="1.0.0",
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ── In-memory job store ───────────────────────────────────────────────────────
# { job_id: { "status": "running|done|error", "logs": deque, "result": dict } }
_jobs: dict[str, dict] = {}

# ── Global activity log (all backend events, streamed to UI) ──────────────────
_global_log: deque = deque(maxlen=2000)

def _glog(msg: str) -> None:
    """Append a timestamped message to the global activity log."""
    _global_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ── Scheduler (singleton) ─────────────────────────────────────────────────────
_scheduler = DailyScheduler()


# ════════════════════════════════════════════════════════════════════════════
# Pydantic models
# ════════════════════════════════════════════════════════════════════════════

class CycleRequest(BaseModel):
    brand_slug: Optional[str] = "luna_silver"
    cycle: str = "full"          # full | monitoring | engagement | content | growth
    week: int = 1                # 1-4

class ScheduleRequest(BaseModel):
    brand_slug: str = "luna_silver"
    monitoring_time: str = "07:00"
    engagement_time: str = "08:00"
    content_time: str = "09:00"
    growth_time: str = "17:00"
    timezone: str = "UTC"

class BrandScheduleRequest(BaseModel):
    """Per-brand schedule config — used by the agency multi-brand endpoint."""
    monitoring_time: str = "07:00"
    engagement_time: str = "08:00"
    content_time: str = "09:00"
    growth_time: str = "17:00"
    timezone: str = "UTC"


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════

def _load_brand(brand_slug: str) -> dict:
    """Load brand profile from storage/db or config/brand_profiles."""
    # Check storage first (user-uploaded brands)
    stored = STORAGE_DIR / brand_slug / "brand_profile.json"
    if stored.exists():
        return json.loads(stored.read_text())

    # Fall back to built-in profiles
    for path in BRAND_PROFILES_DIR.glob("*.json"):
        profile = json.loads(path.read_text())
        from storage.data_store import _slug
        if _slug(profile.get("name", "")) == brand_slug or path.stem == brand_slug:
            return profile

    raise HTTPException(status_code=404, detail=f"Brand '{brand_slug}' not found")


def _append_log(job_id: str, message: str) -> None:
    if job_id in _jobs:
        _jobs[job_id]["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    _glog(message)


def _run_cycle_task(job_id: str, brand_slug: str, cycle: str, week: int) -> None:
    """Background thread: runs the full orchestrator cycle."""
    from orchestrator.orchestrator import Orchestrator
    from rich.console import Console
    import io

    _jobs[job_id]["status"] = "running"
    _append_log(job_id, f"Starting cycle='{cycle}' week={week} brand='{brand_slug}'")

    try:
        brand = _load_brand(brand_slug)
        store = DataStore(brand["name"])

        # Wire the orchestrator to emit logs into our job store
        orch = Orchestrator(brand)

        _append_log(job_id, f"Orchestrator ready — mode={RUN_MODE}")

        if cycle == "full":
            _append_log(job_id, "Phase 1/8: Strategy Agent…")
            results = {}

            month = datetime.now().strftime("%B %Y")
            strategy = orch.strategy_agent.run({
                "brand_profile": brand,
                "past_analytics": brand.get("past_performance", {}),
                "month": month,
            })
            store.save_strategy(strategy)
            results["strategy"] = strategy
            _append_log(job_id, f"✓ Strategy complete — {len(strategy.get('campaign_themes', []))} themes")

            _append_log(job_id, "Phase 2/8: Trend Research Agent…")
            trends = orch.trend_agent.run({"brand_profile": brand, "strategy_plan": strategy})
            store.save_trend_report(trends)
            results["trends"] = trends
            _append_log(job_id, f"✓ Trends complete — {len(trends.get('trending_topics', []))} topics")

            _append_log(job_id, f"Phase 3/8: Campaign Planner (week {week})…")
            campaign = orch.campaign_agent.run({
                "brand_profile": brand, "strategy_plan": strategy,
                "trend_report": trends, "week_number": week,
            })
            store.save_campaign(campaign, week=week)
            results["campaign"] = campaign
            n_posts = campaign.get("weekly_summary", {}).get("total_posts", 0)
            _append_log(job_id, f"✓ Campaign plan complete — {n_posts} posts")

            _append_log(job_id, "Phase 4/8: Content + Visual + Reel Agents…")
            content_packages = orch._run_content_block(campaign, strategy, trends)
            results["content_packages"] = content_packages
            _append_log(job_id, f"✓ Content packages complete — {len(content_packages)} posts")

            _append_log(job_id, "Phase 5/8: Engagement Agent…")
            engagement = orch.engagement_agent.run({"brand_profile": brand})
            store.save_engagement(engagement)
            results["engagement"] = engagement
            leads = engagement.get("summary", {}).get("hot_leads_found", 0)
            _append_log(job_id, f"✓ Engagement complete — {leads} hot leads")

            _append_log(job_id, "Phase 6/8: Scheduler Agent…")
            schedule = orch.scheduler_agent.run({
                "campaign_plan": campaign, "content_packages": content_packages,
                "brand_profile": brand,
            })
            store.save_schedule(schedule, week=week)
            results["schedule"] = schedule
            _append_log(job_id, f"✓ Schedule queued — {schedule.get('publishing_manifest', {}).get('total_posts', 0)} posts")

            _append_log(job_id, "Phase 7/8: Analytics Agent…")
            analytics = orch.analytics_agent.run({
                "brand_profile": brand, "campaign_plan": campaign,
                "published_posts": [], "period": "weekly",
            })
            store.save_analytics(analytics)
            results["analytics"] = analytics
            eng = analytics.get("content_performance", {}).get("avg_engagement_rate", 0)
            _append_log(job_id, f"✓ Analytics complete — avg engagement {eng}%")

            _append_log(job_id, "Phase 8/8: Optimization Agent…")
            optimizations = orch.optimization_agent.run({
                "brand_profile": brand, "analytics_report": analytics,
                "strategy_plan": strategy, "campaign_plan": campaign,
            })
            store.save_optimization(optimizations)
            results["optimizations"] = optimizations
            wins = len(optimizations.get("quick_wins", []))
            _append_log(job_id, f"✓ Optimization complete — {wins} quick wins")

        elif cycle == "monitoring":
            _append_log(job_id, "Running monitoring block…")
            results = orch.run_monitoring_block()
            store.save_trend_report(results.get("trends", {}))
            store.save_analytics(results.get("analytics", {}))

        elif cycle == "engagement":
            _append_log(job_id, "Running engagement block…")
            results = orch.run_engagement_block()
            store.save_engagement(results)

        elif cycle == "content":
            _append_log(job_id, f"Running content block (week {week})…")
            results = orch.run_content_block(week=week)

        elif cycle == "growth":
            _append_log(job_id, "Running growth block…")
            results = orch.run_growth_block(week=week)

        else:
            raise ValueError(f"Unknown cycle: {cycle}")

        _jobs[job_id]["result"] = results
        _jobs[job_id]["status"] = "done"
        _append_log(job_id, f"✅ Cycle '{cycle}' complete!")

    except Exception as exc:
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(exc)
        _append_log(job_id, f"❌ Error: {exc}")


# ════════════════════════════════════════════════════════════════════════════
# Routes — UI
# ════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "run_mode": RUN_MODE,
    })


# ════════════════════════════════════════════════════════════════════════════
# Routes — API
# ════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "run_mode": RUN_MODE,
        "timestamp": datetime.now().isoformat(),
        "active_jobs": sum(1 for j in _jobs.values() if j["status"] == "running"),
    }


@app.get("/api/brands")
async def list_brands():
    brands = []
    # Built-in profiles
    for path in BRAND_PROFILES_DIR.glob("*.json"):
        try:
            p = json.loads(path.read_text())
            from storage.data_store import _slug
            brands.append({
                "slug": _slug(p.get("name", path.stem)),
                "name": p.get("name"),
                "industry": p.get("industry"),
                "instagram_handle": p.get("instagram_handle"),
                "source": "built-in",
            })
        except Exception:
            pass
    # User-uploaded brands
    for brand_dir in STORAGE_DIR.iterdir():
        profile_path = brand_dir / "brand_profile.json"
        if profile_path.exists():
            try:
                p = json.loads(profile_path.read_text())
                from storage.data_store import _slug
                slug = _slug(p.get("name", brand_dir.name))
                if not any(b["slug"] == slug for b in brands):
                    brands.append({
                        "slug": slug,
                        "name": p.get("name"),
                        "industry": p.get("industry"),
                        "instagram_handle": p.get("instagram_handle"),
                        "source": "uploaded",
                    })
            except Exception:
                pass
    return {"brands": brands}


@app.post("/api/brands")
async def upload_brand(request: Request):
    """Accept a raw JSON brand profile and save it."""
    try:
        profile = await request.json()
        if "name" not in profile:
            raise HTTPException(status_code=400, detail="Brand profile must have a 'name' field")
        store = DataStore(profile["name"])
        store.save_brand_profile(profile)
        from storage.data_store import _slug
        slug = _slug(profile["name"])
        _glog(f"Brand saved: '{profile['name']}' (slug={slug})")
        return {"slug": slug, "name": profile["name"], "saved": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/cycle/run")
async def run_cycle(req: CycleRequest, background_tasks: BackgroundTasks):
    """Launch a cycle as a background job. Returns a job_id to poll."""
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "status": "queued",
        "logs": deque(maxlen=500),
        "result": None,
        "error": None,
        "started_at": datetime.now().isoformat(),
        "cycle": req.cycle,
        "brand_slug": req.brand_slug,
        "week": req.week,
    }
    _glog(f"Cycle queued: brand='{req.brand_slug}' cycle='{req.cycle}' week={req.week} job={job_id}")
    background_tasks.add_task(
        _run_cycle_task, job_id, req.brand_slug, req.cycle, req.week
    )
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/cycle/status/{job_id}")
async def cycle_status(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = _jobs[job_id]
    return {
        "job_id": job_id,
        "status": job["status"],
        "started_at": job.get("started_at"),
        "logs": list(job["logs"])[-50:],  # last 50 log lines
        "error": job.get("error"),
        "has_result": job["result"] is not None,
    }


@app.get("/api/stream/{job_id}")
async def stream_logs(job_id: str):
    """Server-Sent Events stream of job logs."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    def event_generator():
        sent = 0
        while True:
            job = _jobs.get(job_id, {})
            logs = list(job.get("logs", []))
            for line in logs[sent:]:
                yield f"data: {json.dumps({'log': line})}\n\n"
                sent += 1
            if job.get("status") in ("done", "error"):
                yield f"data: {json.dumps({'status': job['status'], 'done': True})}\n\n"
                break
            time.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/logs/stream")
async def stream_global_logs():
    """Server-Sent Events stream of all backend activity (global log)."""
    def event_generator():
        sent = 0
        # Immediately send backlog (last 100 lines)
        backlog = list(_global_log)
        for line in backlog:
            yield f"data: {json.dumps({'log': line})}\n\n"
        sent = len(backlog)
        while True:
            current = list(_global_log)
            for line in current[sent:]:
                yield f"data: {json.dumps({'log': line})}\n\n"
                sent = len(current)
            time.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/results/{brand_slug}")
async def get_results(brand_slug: str):
    store = DataStore.__new__(DataStore)
    store.brand_slug = brand_slug
    store.root = STORAGE_DIR / brand_slug
    if not store.root.exists():
        raise HTTPException(status_code=404, detail=f"No data for brand '{brand_slug}'")
    store._init_dirs = lambda: None

    return {
        "brand_slug": brand_slug,
        "strategy": store.load("strategy", _latest_file(store.root / "strategy")),
        "trends": store.load("trends", _latest_file(store.root / "trends")),
        "campaign": store.load("campaigns", _latest_file(store.root / "campaigns")),
        "analytics": store.load("analytics", _latest_file(store.root / "analytics")),
        "optimizations": store.load("optimizations", _latest_file(store.root / "optimizations")),
    }


@app.get("/api/results/{brand_slug}/{section}")
async def get_result_section(brand_slug: str, section: str):
    valid = {"strategy", "trends", "campaign", "analytics", "optimizations", "engagement", "schedules"}
    if section not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid section. Choose from: {valid}")

    folder_map = {
        "campaign": "campaigns",
        "optimizations": "optimizations",
    }
    folder = folder_map.get(section, section)
    root = STORAGE_DIR / brand_slug / folder
    if not root.exists():
        return {"data": None}

    filename = _latest_file(root)
    if not filename:
        return {"data": None}

    path = root / filename
    data = json.loads(path.read_text())
    return {"section": section, "file": filename, "data": data}


@app.get("/api/results/{brand_slug}/content_packages")
async def get_content_packages(brand_slug: str):
    """Return every content/visual/reel package for a brand (one per post)."""
    root = STORAGE_DIR / brand_slug
    if not root.exists():
        return {"brand_slug": brand_slug, "packages": []}
    content_dir = root / "content"
    visual_dir  = root / "visuals"
    reel_dir    = root / "reels"
    packages = []
    if content_dir.exists():
        for f in sorted(content_dir.glob("*.json")):
            post_id = f.stem
            pkg = {"post_id": post_id, "content": json.loads(f.read_text())}
            vf = visual_dir / f"{post_id}.json"
            if vf.exists():
                pkg["visual"] = json.loads(vf.read_text())
            rf = reel_dir / f"{post_id}.json"
            if rf.exists():
                pkg["reel"] = json.loads(rf.read_text())
            packages.append(pkg)
    return {"brand_slug": brand_slug, "packages": packages}


@app.get("/api/schedule")
async def get_schedule():
    return _scheduler.get_status()


@app.post("/api/schedule/enable")
async def enable_schedule(req: ScheduleRequest):
    brand = _load_brand(req.brand_slug)
    result = _scheduler.enable_brand(
        brand_profile=brand,
        monitoring_time=req.monitoring_time,
        engagement_time=req.engagement_time,
        content_time=req.content_time,
        growth_time=req.growth_time,
        timezone=req.timezone,
    )
    return {"enabled": result.get("ok", False), "status": _scheduler.get_status()}


@app.post("/api/schedule/disable")
async def disable_schedule():
    _scheduler.disable_all()
    return {"enabled": False}


# ── Agency: per-brand schedule management ─────────────────────────────────────

@app.get("/api/agency")
async def agency_overview():
    """
    Return a summary of every known brand with KPIs, schedule status,
    last run time, and any errors. Powers the agency dashboard.
    """
    from storage.data_store import _slug as make_slug

    # Collect all known brand slugs (built-in profiles + storage dirs)
    known: dict[str, dict] = {}

    for path in BRAND_PROFILES_DIR.glob("*.json"):
        try:
            p = json.loads(path.read_text())
            slug = make_slug(p.get("name", path.stem))
            known[slug] = {"name": p.get("name"), "industry": p.get("industry"),
                           "handle": p.get("instagram_handle", p.get("social_media", {}).get("instagram", {}).get("handle", "—")),
                           "source": "built-in"}
        except Exception:
            pass

    if STORAGE_DIR.exists():
        for brand_dir in STORAGE_DIR.iterdir():
            bp = brand_dir / "brand_profile.json"
            if bp.exists():
                try:
                    p = json.loads(bp.read_text())
                    slug = make_slug(p.get("name", brand_dir.name))
                    if slug not in known:
                        known[slug] = {"name": p.get("name"), "industry": p.get("industry"),
                                       "handle": p.get("instagram_handle", "—"), "source": "uploaded"}
                except Exception:
                    pass

    schedule_status = _scheduler.get_status()
    scheduled_brands = {b["brand_slug"]: b for b in schedule_status.get("brands", [])}

    brands_out = []
    for slug, info in known.items():
        # Latest KPIs
        analytics = None
        optimizations = None
        analytics_dir = STORAGE_DIR / slug / "analytics"
        opt_dir       = STORAGE_DIR / slug / "optimizations"
        if analytics_dir.exists():
            files = sorted(analytics_dir.glob("*.json"))
            if files:
                try:
                    analytics = json.loads(files[-1].read_text())
                except Exception:
                    pass
        if opt_dir.exists():
            files = sorted(opt_dir.glob("*.json"))
            if files:
                try:
                    optimizations = json.loads(files[-1].read_text())
                except Exception:
                    pass

        # Last run time
        last_run = None
        for cat in ("analytics", "optimizations", "engagement"):
            cat_dir = STORAGE_DIR / slug / cat
            if cat_dir.exists():
                files = sorted(cat_dir.glob("*.json"))
                if files:
                    last_run = files[-1].stem.split("_")[0]
                    break

        sched = scheduled_brands.get(slug, {})
        brands_out.append({
            "slug": slug,
            "name": info["name"],
            "industry": info.get("industry"),
            "handle": info.get("handle"),
            "source": info.get("source"),
            "scheduled": bool(sched),
            "schedule": sched.get("times"),
            "next_runs": sched.get("jobs", []),
            "timezone": sched.get("timezone"),
            "last_run": last_run,
            "kpis": {
                "followers_gained": (analytics or {}).get("account_metrics", {}).get("followers_gained", "—"),
                "engagement_rate":  (analytics or {}).get("content_performance", {}).get("avg_engagement_rate", "—"),
                "hot_leads":        (analytics or {}).get("dm_funnel", {}).get("new_dms", "—"),
                "verdict":          (optimizations or {}).get("performance_verdict", "—"),
            },
        })

    return {
        "total_brands": len(brands_out),
        "scheduled_brands": len(scheduled_brands),
        "brands": brands_out,
    }


@app.post("/api/brands/{brand_slug}/schedule/enable")
async def enable_brand_schedule(brand_slug: str, req: BrandScheduleRequest):
    """Enable daily automation for a single brand."""
    _glog(f"Schedule ENABLED for brand='{brand_slug}' timezone={req.timezone}")
    brand = _load_brand(brand_slug)
    result = _scheduler.enable_brand(
        brand_profile=brand,
        monitoring_time=req.monitoring_time,
        engagement_time=req.engagement_time,
        content_time=req.content_time,
        growth_time=req.growth_time,
        timezone=req.timezone,
    )
    return result


@app.post("/api/brands/{brand_slug}/schedule/disable")
async def disable_brand_schedule(brand_slug: str):
    """Disable daily automation for a single brand."""
    _glog(f"Schedule DISABLED for brand='{brand_slug}'")
    _scheduler.disable_brand(brand_slug)
    return {"disabled": True, "brand_slug": brand_slug}


@app.get("/api/brands/{brand_slug}/schedule")
async def get_brand_schedule(brand_slug: str):
    """Get schedule status for a single brand."""
    status = _scheduler.get_brand_status(brand_slug)
    if status is None:
        return {"brand_slug": brand_slug, "scheduled": False}
    return {"brand_slug": brand_slug, "scheduled": True, **status}


# ════════════════════════════════════════════════════════════════════════════
# OAuth — Instagram / Meta connection
# ════════════════════════════════════════════════════════════════════════════

@app.get("/api/oauth/connect/{brand_slug}")
async def oauth_connect(brand_slug: str, request: Request):
    """
    Redirect the user to the Meta OAuth dialog.
    After approving, Meta sends them back to /api/oauth/callback.
    """
    from api.oauth import get_oauth_url
    from config.settings import META_APP_ID
    if not META_APP_ID:
        raise HTTPException(
            status_code=400,
            detail="META_APP_ID is not set. Add it to your .env file first."
        )
    redirect_uri = str(request.base_url).rstrip("/") + "/api/oauth/callback"
    url = get_oauth_url(brand_slug, redirect_uri)
    _glog(f"OAuth flow started for brand='{brand_slug}'")
    return RedirectResponse(url)


@app.get("/api/oauth/callback")
async def oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    """
    Meta OAuth callback.
    Exchanges code → long-lived token → fetches IG account ID → saves to brand profile.
    Redirects back to the UI with ?oauth=success or ?oauth=error.
    """
    if error:
        msg = error_description or error
        _glog(f"OAuth denied/error for brand='{state}': {msg}")
        return RedirectResponse(f"/?oauth=error&msg={msg[:120]}")

    if not code or not state:
        return RedirectResponse("/?oauth=error&msg=missing_code_or_state")

    brand_slug = state
    redirect_uri = str(request.base_url).rstrip("/") + "/api/oauth/callback"

    try:
        from api.oauth import exchange_code_for_token, fetch_instagram_account, save_credentials_to_brand

        _glog(f"OAuth: exchanging code for brand='{brand_slug}'...")
        token_data = exchange_code_for_token(code, redirect_uri)

        _glog(f"OAuth: fetching Instagram account for brand='{brand_slug}'...")
        account_data = fetch_instagram_account(token_data["access_token"])

        save_credentials_to_brand(brand_slug, token_data, account_data)
        _glog(
            f"OAuth SUCCESS: brand='{brand_slug}' "
            f"ig_account={account_data['instagram_account_id']} "
            f"token_expires_in={token_data.get('expires_in_days', '?')}d"
        )
        return RedirectResponse(
            f"/?oauth=success&brand={brand_slug}"
            f"&ig={account_data['instagram_account_id']}"
        )

    except Exception as exc:
        _glog(f"OAuth FAILED for brand='{brand_slug}': {exc}")
        safe_msg = str(exc)[:150].replace("&", "and")
        return RedirectResponse(f"/?oauth=error&brand={brand_slug}&msg={safe_msg}")


@app.get("/api/brands/{brand_slug}/oauth/status")
async def brand_oauth_status(brand_slug: str):
    """Return the Instagram connection status for a brand."""
    try:
        profile = _load_brand(brand_slug)
        from api.oauth import get_token_status
        return get_token_status(profile)
    except Exception:
        return {"status": "not_connected", "label": "Not Connected", "ig_account_id": None}


# ── Background token refresh (runs every 12 hours) ────────────────────────────

def _auto_refresh_tokens() -> None:
    """Check all brands and refresh any token expiring within 7 days."""
    try:
        from api.oauth import refresh_all_expiring_tokens
        refreshed = refresh_all_expiring_tokens(glog_fn=_glog)
        if refreshed:
            _glog(f"Auto-refresh: refreshed tokens for {len(refreshed)} brand(s): {', '.join(refreshed)}")
    except Exception as exc:
        _glog(f"Auto-refresh error: {exc}")


@app.on_event("startup")
async def _start_token_refresh_job():
    from apscheduler.schedulers.background import BackgroundScheduler as _BGScheduler
    _bg = _BGScheduler()
    _bg.add_job(_auto_refresh_tokens, "interval", hours=12, id="token_refresh",
                misfire_grace_time=3600)
    _bg.start()
    _glog("Token refresh scheduler started (runs every 12h)")


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════

def _latest_file(directory: Path) -> Optional[str]:
    files = sorted(f.name for f in directory.glob("*.json")) if directory.exists() else []
    return files[-1] if files else None


# ════════════════════════════════════════════════════════════════════════════
# Entry point (local dev)
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api.app:app", host="0.0.0.0", port=port, reload=True)
