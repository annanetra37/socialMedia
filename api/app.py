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

import shutil

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from api.scheduler import AgencyScheduler as DailyScheduler
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

# ── Anthropic model pricing (USD per million tokens) ─────────────────────────
_MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6":   {"input": 15.00, "output": 75.00, "cache_read": 1.50,  "cache_write": 18.75},
    "claude-sonnet-4-6": {"input":  3.00, "output": 15.00, "cache_read": 0.30,  "cache_write":  3.75},
    "claude-haiku-4-5":  {"input":  0.80, "output":  4.00, "cache_read": 0.08,  "cache_write":  1.00},
}
_DEFAULT_PRICING = _MODEL_PRICING["claude-opus-4-6"]

def _compute_cost(usage: dict, model: str = "") -> float:
    p = _MODEL_PRICING.get(model, _DEFAULT_PRICING)
    m = 1_000_000
    return (
        usage.get("input_tokens", 0)       / m * p["input"]
        + usage.get("output_tokens", 0)    / m * p["output"]
        + usage.get("cache_read_tokens", 0)  / m * p["cache_read"]
        + usage.get("cache_write_tokens", 0) / m * p["cache_write"]
    )

def _merge_agent_usage(total: dict, agent) -> None:
    for key in total:
        total[key] += agent._usage.get(key, 0)

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
    """Load brand profile from DB → filesystem storage → built-in profiles."""
    import os
    if os.getenv("DATABASE_URL"):
        from storage.database import get_brand as db_get
        profile = db_get(brand_slug)
        if profile:
            return profile
    else:
        stored = STORAGE_DIR / brand_slug / "brand_profile.json"
        if stored.exists():
            return json.loads(stored.read_text())

    # Fall back to built-in profiles
    from storage.data_store import _slug
    for path in BRAND_PROFILES_DIR.glob("*.json"):
        profile = json.loads(path.read_text())
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
            results = {}
            month = datetime.now().strftime("%B %Y")

            _append_log(job_id, "Phase 1/8: Trend Research Agent…")
            trends = orch.trend_agent.run({"brand_profile": brand, "strategy_plan": {}})
            store.save_trend_report(trends)
            results["trends"] = trends
            _append_log(job_id, f"✓ Trends complete — {len(trends.get('trending_topics', []))} topics")

            _append_log(job_id, "Phase 2/8: Strategy Agent…")
            strategy = orch.strategy_agent.run({
                "brand_profile": brand,
                "past_analytics": brand.get("past_performance", {}),
                "trend_report": trends,
                "month": month,
            })
            store.save_strategy(strategy)
            results["strategy"] = strategy
            _append_log(job_id, f"✓ Strategy complete — {len(strategy.get('campaign_themes', []))} themes")

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
            _append_log(job_id, "Checking for strategy, trends, and campaign prerequisites…")
            results = orch.run_content_block(week=week)
            n_pkgs = len(results.get("content_packages", []))
            _append_log(job_id, f"✓ Content complete — {n_pkgs} packages generated")

        elif cycle == "growth":
            _append_log(job_id, "Running growth block (scheduling + optimization)…")
            results = orch.run_growth_block(week=week)

        elif cycle == "strategy":
            _append_log(job_id, "Phase 1/1: Strategy Agent — generating monthly strategy…")
            results = orch.run_strategy_block()
            n = len(results.get("strategy", {}).get("campaign_themes", []))
            _append_log(job_id, f"✓ Strategy complete — {n} campaign themes")

        elif cycle == "trends":
            _append_log(job_id, "Phase 1/1: Trend Research Agent…")
            results = orch.run_trends_block()
            n = len(results.get("trends", {}).get("trending_topics", []))
            _append_log(job_id, f"✓ Trends complete — {n} topics found")

        elif cycle == "campaign":
            _append_log(job_id, f"Phase 1/1: Campaign Planner — Week {week}…")
            _append_log(job_id, "Loading strategy + trends (auto-generates if missing)…")
            results = orch.run_campaign_block(week=week)
            posts = results.get("campaign", {}).get("posts", [])
            _append_log(job_id, f"✓ Campaign complete — {len(posts)} posts planned for Week {week}")

        elif cycle == "analytics":
            _append_log(job_id, "Phase 1/1: Analytics Agent…")
            results = orch.run_analytics_block()
            eng = results.get("analytics", {}).get("content_performance", {}).get("avg_engagement_rate", "?")
            _append_log(job_id, f"✓ Analytics complete — avg engagement rate: {eng}%")

        elif cycle == "optimization":
            _append_log(job_id, "Phase 1/1: Optimization Agent…")
            results = orch.run_optimization_block(week=week)
            wins = len(results.get("optimizations", {}).get("quick_wins", []))
            _append_log(job_id, f"✓ Optimization complete — {wins} quick wins")

        else:
            raise ValueError(f"Unknown cycle: {cycle}")

        # Aggregate token usage from all agents
        all_agents = [
            orch.strategy_agent, orch.trend_agent, orch.campaign_agent,
            orch.content_agent, orch.visual_agent, orch.reel_agent,
            orch.engagement_agent, orch.scheduler_agent,
            orch.analytics_agent, orch.optimization_agent,
        ]
        for agent in all_agents:
            _merge_agent_usage(_jobs[job_id]["usage"], agent)
        _jobs[job_id]["model"] = orch.strategy_agent.model

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
    import os
    from storage.data_store import _slug
    brands = []

    # Built-in profiles (always from filesystem)
    for path in BRAND_PROFILES_DIR.glob("*.json"):
        try:
            p = json.loads(path.read_text())
            brands.append({
                "slug": _slug(p.get("name", path.stem)),
                "name": p.get("name"),
                "industry": p.get("industry"),
                "instagram_handle": p.get("instagram_handle"),
                "source": "built-in",
            })
        except Exception:
            pass

    # User-uploaded brands — DB or filesystem
    if os.getenv("DATABASE_URL"):
        from storage.database import list_brands as db_list
        for row in db_list():
            if not any(b["slug"] == row["slug"] for b in brands):
                brands.append({
                    "slug": row["slug"],
                    "name": row["name"],
                    "industry": row.get("industry"),
                    "instagram_handle": row.get("instagram_handle"),
                    "source": "uploaded",
                })
    else:
        for brand_dir in STORAGE_DIR.iterdir():
            profile_path = brand_dir / "brand_profile.json"
            if profile_path.exists():
                try:
                    p = json.loads(profile_path.read_text())
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


@app.get("/api/brands/{brand_slug}/profile")
async def get_brand_profile(brand_slug: str):
    """Return full brand profile for a given slug."""
    return _load_brand(brand_slug)


@app.put("/api/brands/{brand_slug}")
async def update_brand(brand_slug: str, request: Request):
    """Overwrite a brand's profile (keeps meta_credentials intact)."""
    import os
    try:
        new_profile = await request.json()
        if "name" not in new_profile:
            raise HTTPException(status_code=400, detail="Brand profile must have a 'name' field")
        # Load existing to preserve OAuth credentials
        existing = _load_brand(brand_slug)
        for key in ("meta_credentials", "instagram_account_id", "facebook_page_id"):
            if key in existing and key not in new_profile:
                new_profile[key] = existing[key]
        store = DataStore(new_profile["name"])
        store.save_brand_profile(new_profile)
        _glog(f"Brand updated: '{new_profile['name']}' (slug={brand_slug})")
        return {"slug": brand_slug, "name": new_profile["name"], "saved": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/brands/{brand_slug}")
async def delete_brand(brand_slug: str):
    """Delete a user-uploaded brand and all its data."""
    import os
    deleted = False
    if os.getenv("DATABASE_URL"):
        from storage.database import delete_brand as db_del, get_brand
        if not get_brand(brand_slug):
            raise HTTPException(status_code=404, detail=f"Brand '{brand_slug}' not found")
        db_del(brand_slug)
        deleted = True
    else:
        brand_dir = STORAGE_DIR / brand_slug
        if not brand_dir.exists():
            raise HTTPException(status_code=404, detail=f"Brand '{brand_slug}' not found")
        shutil.rmtree(brand_dir)
        deleted = True
    if deleted:
        _glog(f"Brand deleted: '{brand_slug}'")
    return {"deleted": deleted, "slug": brand_slug}


_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_IMAGE_EXTS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


@app.post("/api/brands/{brand_slug}/products/{product_idx}/image")
async def upload_product_image(brand_slug: str, product_idx: int, file: UploadFile = File(...)):
    """Upload a product photo."""
    import os
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG and WebP images are allowed")
    contents = await file.read()
    if os.getenv("DATABASE_URL"):
        from storage.database import upsert_product_image
        upsert_product_image(brand_slug, product_idx, contents, file.content_type or "image/jpeg")
    else:
        img_dir = STORAGE_DIR / brand_slug / "product_images"
        img_dir.mkdir(parents=True, exist_ok=True)
        ext = _IMAGE_EXTS.get(file.content_type, ".jpg")
        for old in img_dir.glob(f"{product_idx}.*"):
            old.unlink(missing_ok=True)
        (img_dir / f"{product_idx}{ext}").write_bytes(contents)
    return {"saved": True, "url": f"/api/brands/{brand_slug}/products/{product_idx}/image"}


@app.get("/api/brands/{brand_slug}/products/{product_idx}/image")
async def serve_product_image(brand_slug: str, product_idx: int):
    """Serve a product photo."""
    import os
    from fastapi.responses import Response
    if os.getenv("DATABASE_URL"):
        from storage.database import get_product_image
        result = get_product_image(brand_slug, product_idx)
        if result:
            data, ct = result
            return Response(content=data, media_type=ct)
    else:
        img_dir = STORAGE_DIR / brand_slug / "product_images"
        for ext in (".jpg", ".png", ".webp"):
            p = img_dir / f"{product_idx}{ext}"
            if p.exists():
                return FileResponse(str(p))
    raise HTTPException(status_code=404, detail="No image found")


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
        "usage": {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0},
        "model": "",
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
    usage = job.get("usage", {})
    model = job.get("model", "")
    return {
        "job_id": job_id,
        "status": job["status"],
        "started_at": job.get("started_at"),
        "logs": list(job["logs"])[-50:],
        "error": job.get("error"),
        "has_result": job["result"] is not None,
        "usage": usage,
        "cost_usd": round(_compute_cost(usage, model), 6),
        "model": model,
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
    store = DataStore.from_slug(brand_slug)
    return {
        "brand_slug": brand_slug,
        "strategy":      store.load_latest("strategy"),
        "trends":        store.load_latest("trends"),
        "campaign":      store.load_latest("campaigns"),
        "analytics":     store.load_latest("analytics"),
        "optimizations": store.load_latest("optimizations"),
    }


# IMPORTANT: This route MUST be defined BEFORE the /{section} catch-all below,
# otherwise FastAPI matches "content_packages" as a {section} parameter and
# returns 400 because it's not in the valid set.
@app.get("/api/results/{brand_slug}/content_packages")
async def get_content_packages(brand_slug: str):
    """Return every content/visual/reel package for a brand (one per post).

    Merges scheduling metadata from ALL campaign plans (not just the latest)
    into each content package so the frontend has everything it needs.
    """
    import re as _re
    store = DataStore.from_slug(brand_slug)

    # Build a lookup from post_id → campaign post metadata across ALL weeks
    post_meta: dict[str, dict] = {}
    for campaign in store.load_all("campaigns"):
        week_num = campaign.get("week_number", 1)
        for p in campaign.get("posts", []):
            pid = p.get("id") or p.get("post_id")
            if pid:
                p.setdefault("week", week_num)
                post_meta[pid] = p

    def _extract_week(post_id: str) -> int:
        """Extract week number from post_id like 'post_w2_5' → 2."""
        m = _re.search(r"_w(\d+)", post_id)
        return int(m.group(1)) if m else 1

    packages = []
    for fname in store.list_files("content"):
        post_id = fname.removesuffix(".json")
        content = store.load("content", fname) or {}
        meta = post_meta.get(post_id, {})

        # Extract caption object — the content agent nests it under "caption"
        caption_data = content.get("caption", {})

        pkg = {
            # Scheduling metadata: prefer campaign plan, fall back to content data
            "post_id":      post_id,
            "type":         meta.get("type") or content.get("post_type", "image"),
            "day":          meta.get("day", ""),
            "date":         meta.get("date", ""),
            "time":         meta.get("time") or content.get("best_time_to_post", ""),
            "priority":     meta.get("priority", "medium"),
            "week":         meta.get("week") or _extract_week(post_id),
            "trend_format": meta.get("trend_format", ""),
            "theme":        meta.get("theme", ""),
            "hook":         meta.get("hook") or (caption_data.get("hook", "") if isinstance(caption_data, dict) else ""),
            # Content data from content/visual/reel agents
            "caption":      caption_data,
            "hashtags":     content.get("hashtags", content.get("hashtag_cluster", [])),
            "alt_text":     content.get("alt_text", ""),
            "content_notes": content.get("content_notes", ""),
            "visual":       store.load("visuals", fname),
            "reel":         store.load("reels", fname),
        }
        packages.append(pkg)
    return {"brand_slug": brand_slug, "packages": packages}


@app.get("/api/results/{brand_slug}/{section}")
async def get_result_section(brand_slug: str, section: str):
    valid = {"strategy", "trends", "campaign", "analytics", "optimizations", "engagement", "schedules"}
    if section not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid section. Choose from: {valid}")
    folder_map = {"campaign": "campaigns"}
    folder = folder_map.get(section, section)
    store = DataStore.from_slug(brand_slug)
    data = store.load_latest(folder)
    if data is None:
        return {"data": None}
    files = store.list_files(folder)
    return {"section": section, "file": files[-1] if files else None, "data": data}


@app.put("/api/brands/{brand_slug}/content/{post_id}")
async def update_content(brand_slug: str, post_id: str, request: Request):
    """Update a content package (caption, hashtags, etc.) in-place."""
    store = DataStore.from_slug(brand_slug)
    existing = store.load("content", f"{post_id}.json")
    if not existing:
        raise HTTPException(status_code=404, detail=f"No content for '{post_id}'")

    body = await request.json()
    # Merge updates into existing content
    if "caption" in body:
        cap = body["caption"]
        if isinstance(cap, dict):
            existing.setdefault("caption", {}).update(cap)
            # Rebuild full_caption from parts
            parts = [existing["caption"].get("hook", ""),
                     existing["caption"].get("body", ""),
                     existing["caption"].get("cta", "")]
            ht = existing.get("hashtags", {})
            full_set = ht.get("full_set", "") if isinstance(ht, dict) else ""
            existing["caption"]["full_caption"] = "\n\n".join(p for p in parts if p)
            if full_set:
                existing["caption"]["full_caption"] += "\n\n" + full_set
            existing["caption"]["character_count"] = len(existing["caption"]["full_caption"])
        else:
            existing["caption"] = cap
    if "hashtags" in body:
        existing["hashtags"] = body["hashtags"]
    if "alt_text" in body:
        existing["alt_text"] = body["alt_text"]
    if "content_notes" in body:
        existing["content_notes"] = body["content_notes"]

    store.save_content(existing, post_id)
    return {"status": "updated", "post_id": post_id}


@app.post("/api/brands/{brand_slug}/posts/{post_id}/publish-now")
async def publish_post_now(brand_slug: str, post_id: str):
    """Immediately publish a saved content package to Instagram."""
    from tools.instagram_api import InstagramAPI

    brand = _load_brand(brand_slug)
    store = DataStore.from_slug(brand_slug)

    content = store.load("content", f"{post_id}.json")
    if not content:
        raise HTTPException(status_code=404, detail=f"No content package for '{post_id}'. Run a content cycle first.")

    # Build caption
    caption_data = content.get("caption", {})
    if isinstance(caption_data, dict):
        caption = caption_data.get("full_caption") or "\n\n".join(
            filter(None, [caption_data.get("hook"), caption_data.get("body"), caption_data.get("cta")])
        )
    else:
        caption = str(caption_data)

    hashtags = content.get("hashtags", {})
    ht = hashtags.get("full_set", "") if isinstance(hashtags, dict) else (" ".join(hashtags) if isinstance(hashtags, list) else "")
    if ht:
        caption = caption.strip() + "\n\n" + ht

    # Try to get a media URL from the saved visual package
    visual = store.load("visuals", f"{post_id}.json")
    media_url = ""
    if visual:
        media_url = (
            visual.get("image_url")
            or visual.get("media_url")
            or visual.get("primary_image", {}).get("url", "")
            or visual.get("primary_image", {}).get("generated_url", "")
        )

    api = InstagramAPI(brand)
    result = api.schedule_post({
        "post_id": post_id,
        "caption": caption.strip(),
        "media_url": media_url,
        "post_type": content.get("post_type", "image"),
    })
    _glog(f"Manual publish: brand='{brand_slug}' post='{post_id}' → {result.get('status')}")
    return {"post_id": post_id, "brand_slug": brand_slug, "result": result}


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

    import os
    if os.getenv("DATABASE_URL"):
        from storage.database import list_brands as db_list
        for row in db_list():
            slug = row["slug"]
            if slug not in known:
                known[slug] = {"name": row["name"], "industry": row.get("industry"),
                               "handle": row.get("instagram_handle", "—"), "source": "uploaded"}
    elif STORAGE_DIR.exists():
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
        store = DataStore.from_slug(slug)
        analytics = store.load_latest_analytics()
        optimizations = store.load_latest_optimization()

        # Last run time: look at most recently updated analytics/optimizations/engagement key
        last_run = None
        for cat in ("analytics", "optimizations", "engagement"):
            keys = store.list_files(cat)
            if keys:
                last_run = keys[-1].removesuffix(".json").split("_")[0]
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
async def oauth_callback(request: Request):
    """
    Meta OAuth callback.
    Exchanges code → long-lived token → fetches IG account ID → saves to brand profile.
    Redirects back to the UI with ?oauth=success or ?oauth=error.
    """
    params = dict(request.query_params)
    code  = params.get("code")
    state = params.get("state")

    # Facebook uses several different error param names depending on the error type
    error = (params.get("error") or params.get("error_code") or "")
    error_msg = (
        params.get("error_description")
        or params.get("error_message")
        or params.get("error_reason")
        or error
    )

    if error:
        _glog(f"OAuth error for brand='{state}': {error_msg} (raw params: {params})")
        safe = error_msg.replace(" ", "+")[:200]
        return RedirectResponse(f"/?oauth=error&brand={state or ''}&msg={safe}")

    if not code or not state:
        _glog(f"OAuth callback missing code/state. Received params: {params}")
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
async def _startup():
    import asyncio
    import os
    # Init PostgreSQL schema — run in thread so blocking psycopg2 doesn't
    # stall the event loop and cause health-check timeouts.
    if os.getenv("DATABASE_URL"):
        try:
            from storage.database import init_db
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, init_db)
            _glog("PostgreSQL schema initialised")
        except Exception as exc:
            _glog(f"WARNING: DB init failed — {exc}")

    # Token-refresh background job
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
