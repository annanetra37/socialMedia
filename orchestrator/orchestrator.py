"""
Orchestrator — the conductor of the AI Social Media OS.

Runs four daily blocks:
  🔍 MONITORING   → Trend Research + Analytics review
  💬 ENGAGEMENT   → Engagement Agent processes comments/DMs
  ✍️  CONTENT      → Content + Visual + Reel generation for planned posts
  📈 GROWTH        → Campaign planning, scheduling, optimization

Also runs monthly and weekly planning cycles.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.rule import Rule
from rich.table import Table

from agents import (
    AnalyticsAgent,
    CampaignPlannerAgent,
    ContentAgent,
    EngagementAgent,
    OptimizationAgent,
    ReelAgent,
    SchedulerAgent,
    StrategyAgent,
    TrendResearchAgent,
    VisualAgent,
)
from config.settings import RUN_MODE
from storage.data_store import DataStore


class Orchestrator:
    """
    High-level pipeline coordinator.

    Usage:
        orch = Orchestrator(brand_profile)
        orch.run_full_cycle(week_number=1)
        # or individual blocks:
        orch.run_monitoring_block()
        orch.run_engagement_block()
        orch.run_content_block()
        orch.run_growth_block()
    """

    def __init__(self, brand_profile: dict):
        self.brand = brand_profile
        self.console = Console()
        self.store = DataStore(brand_profile["name"])

        # Initialise all agents (they share the same console)
        agent_kwargs = {"console": self.console}
        self.strategy_agent = StrategyAgent(**agent_kwargs)
        self.trend_agent = TrendResearchAgent(**agent_kwargs)
        self.campaign_agent = CampaignPlannerAgent(**agent_kwargs)
        self.content_agent = ContentAgent(**agent_kwargs)
        self.visual_agent = VisualAgent(**agent_kwargs)
        self.reel_agent = ReelAgent(**agent_kwargs)
        self.engagement_agent = EngagementAgent(**agent_kwargs)
        self.scheduler_agent = SchedulerAgent(**agent_kwargs)
        self.analytics_agent = AnalyticsAgent(**agent_kwargs)
        self.optimization_agent = OptimizationAgent(**agent_kwargs)

    # ══════════════════════════════════════════════════════════════════════════
    # PUBLIC: full cycle
    # ══════════════════════════════════════════════════════════════════════════

    def run_full_cycle(self, week_number: int = 1) -> dict:
        """
        Run the complete AI Social Media OS cycle:
        1. Trend Research (brand-only — fresh market data first)
        2. Monthly Strategy (informed by trends + analytics)
        3. Campaign Planning (for specified week)
        4. Content + Visual + Reel generation
        5. Engagement processing
        6. Scheduling
        7. Analytics
        8. Optimization (feeds back to strategy)
        """
        self._print_cycle_header(week_number)
        results: dict = {}
        month = datetime.now().strftime("%B %Y")

        # ── 1. Trend Research (runs first — brand profile only) ──────────────
        trends = self._run_phase(
            "🔍 TREND RESEARCH", "Scanning latest trends",
            lambda: self._run_trends(),
        )
        results["trends"] = trends
        self.store.save_trend_report(trends)

        # ── 2. Strategy (informed by fresh trends) ───────────────────────────
        strategy = self._run_phase(
            "📋 STRATEGY", "Monthly strategy generation",
            lambda: self._run_strategy(month, trends),
        )
        results["strategy"] = strategy
        self.store.save_strategy(strategy)

        # ── 3. Campaign Planning ───────────────────────────────────────────────
        campaign = self._run_phase(
            "📅 CAMPAIGN PLANNING", f"Week {week_number} calendar",
            lambda: self._run_campaign(strategy, trends, week_number),
        )
        results["campaign"] = campaign
        self.store.save_campaign(campaign, week=week_number)

        # ── 4. Content Block ───────────────────────────────────────────────────
        content_packages = self._run_phase(
            "✍️  CONTENT CREATION", "Generating captions, visuals, reel scripts",
            lambda: self._run_content_block(campaign, strategy, trends),
        )
        results["content_packages"] = content_packages

        # ── 5. Engagement Block ────────────────────────────────────────────────
        engagement = self._run_phase(
            "💬 ENGAGEMENT", "Processing comments and DMs",
            lambda: self._run_engagement(),
        )
        results["engagement"] = engagement
        self.store.save_engagement(engagement)

        # ── 6. Scheduling ──────────────────────────────────────────────────────
        schedule = self._run_phase(
            "🗓️  SCHEDULING", "Queuing posts for publishing",
            lambda: self._run_scheduling(campaign, content_packages),
        )
        results["schedule"] = schedule
        self.store.save_schedule(schedule, week=week_number)

        # ── 7. Analytics ───────────────────────────────────────────────────────
        analytics = self._run_phase(
            "📊 ANALYTICS", "Analysing performance data",
            lambda: self._run_analytics(campaign),
        )
        results["analytics"] = analytics
        self.store.save_analytics(analytics)

        # ── 8. Optimization ────────────────────────────────────────────────────
        optimizations = self._run_phase(
            "⚙️  OPTIMIZATION", "Generating improvements for next cycle",
            lambda: self._run_optimization(analytics, strategy, campaign),
        )
        results["optimizations"] = optimizations
        self.store.save_optimization(optimizations)

        self._print_cycle_summary(results)
        return results

    # ══════════════════════════════════════════════════════════════════════════
    # PUBLIC: individual daily blocks
    # ══════════════════════════════════════════════════════════════════════════

    def run_monitoring_block(self) -> dict:
        """Block A: Monitoring — trends + analytics review."""
        self._print_block_header("A", "MONITORING", "🔍")
        strategy = self.store.load_strategy() or {}
        trends = self._run_trends(strategy)
        self.store.save_trend_report(trends)

        analytics = self._run_analytics({})
        self.store.save_analytics(analytics)

        return {"trends": trends, "analytics": analytics}

    def run_engagement_block(self) -> dict:
        """Block B: Engagement — comments, DMs, lead qualification."""
        self._print_block_header("B", "ENGAGEMENT", "💬")
        result = self._run_engagement()
        self.store.save_engagement(result)
        return result

    def run_content_block(self, week: int = 1) -> dict:
        """Block C: Content — generate content packages for the week's posts.

        Automatically runs prerequisite agents (strategy → trends → campaign)
        if they haven't been generated yet for this brand.
        """
        self._print_block_header("C", "CONTENT CREATION", "✍️")
        month = datetime.now().strftime("%B %Y")

        strategy = self.store.load_strategy() or {}
        if not strategy:
            self.console.print("  [dim]No strategy found — generating strategy first…[/dim]")
            strategy = self._run_strategy(month)
            self.store.save_strategy(strategy)

        trends = self.store.load_trend_report() or {}
        if not trends:
            self.console.print("  [dim]No trend report found — generating trends first…[/dim]")
            trends = self._run_trends(strategy)
            self.store.save_trend_report(trends)

        campaign = self.store.load_campaign(week=week)
        # Regenerate if missing OR if the stored campaign has no posts
        if not campaign or not campaign.get("posts"):
            self.console.print(f"  [dim]No campaign for week {week} — generating campaign first…[/dim]")
            campaign = self._run_campaign(strategy, trends, week)
            self.store.save_campaign(campaign, week=week)

        packages = self._run_content_block(campaign, strategy, trends)
        return {"campaign": campaign, "content_packages": packages}

    def run_growth_block(self, week: int = 1) -> dict:
        """Block D: Growth — scheduling + optimization recommendations."""
        self._print_block_header("D", "GROWTH ACTIVITIES", "📈")
        campaign = self.store.load_campaign(week=week) or {}
        content_files = [
            self.store.load_content(p["id"])
            for p in campaign.get("posts", [])
            if self.store.load_content(p["id"])
        ]
        schedule = self._run_scheduling(campaign, content_files)
        self.store.save_schedule(schedule, week=week)

        analytics = self.store.load_latest_analytics() or {}
        strategy = self.store.load_strategy() or {}
        optimizations = self._run_optimization(analytics, strategy, campaign)
        self.store.save_optimization(optimizations)

        return {"schedule": schedule, "optimizations": optimizations}

    # ── Granular single-phase blocks ──────────────────────────────────────────

    def run_strategy_block(self) -> dict:
        """Run just the Strategy Agent (loads trends if available)."""
        self._print_block_header("2", "STRATEGY", "📋")
        month = datetime.now().strftime("%B %Y")
        trends = self.store.load_trend_report() or {}
        strategy = self._run_strategy(month, trends)
        self.store.save_strategy(strategy)
        return {"strategy": strategy}

    def run_trends_block(self) -> dict:
        """Run just the Trend Research Agent (brand-only, no strategy needed)."""
        self._print_block_header("1", "TREND RESEARCH", "🔍")
        trends = self._run_trends()
        self.store.save_trend_report(trends)
        return {"trends": trends}

    def run_campaign_block(self, week: int = 1) -> dict:
        """Run just the Campaign Planner Agent (auto-generates prerequisites if missing)."""
        self._print_block_header("3", "CAMPAIGN PLANNER", "📅")
        month = datetime.now().strftime("%B %Y")
        # Trends first (brand-only)
        trends = self.store.load_trend_report() or {}
        if not trends:
            self.console.print("  [dim]No trend report — generating trends first…[/dim]")
            trends = self._run_trends()
            self.store.save_trend_report(trends)
        # Strategy second (informed by trends)
        strategy = self.store.load_strategy() or {}
        if not strategy:
            self.console.print("  [dim]No strategy found — generating strategy first…[/dim]")
            strategy = self._run_strategy(month, trends)
            self.store.save_strategy(strategy)
        campaign = self._run_campaign(strategy, trends, week)
        self.store.save_campaign(campaign, week=week)
        return {"campaign": campaign, "strategy": strategy, "trends": trends}

    def run_analytics_block(self) -> dict:
        """Run just the Analytics Agent."""
        self._print_block_header("7", "ANALYTICS", "📊")
        campaign = self.store.load_campaign() or {}
        analytics = self._run_analytics(campaign)
        self.store.save_analytics(analytics)
        return {"analytics": analytics}

    def run_optimization_block(self, week: int = 1) -> dict:
        """Run just the Optimization Agent."""
        self._print_block_header("8", "OPTIMIZATION", "⚙️")
        analytics = self.store.load_latest_analytics() or {}
        strategy = self.store.load_strategy() or {}
        campaign = self.store.load_campaign(week=week) or {}
        optimizations = self._run_optimization(analytics, strategy, campaign)
        self.store.save_optimization(optimizations)
        return {"optimizations": optimizations}

    # ══════════════════════════════════════════════════════════════════════════
    # PRIVATE: individual agent runners
    # ══════════════════════════════════════════════════════════════════════════

    def _run_strategy(self, month: str, trends: dict | None = None) -> dict:
        return self.strategy_agent.run({
            "brand_profile": self.brand,
            "past_analytics": self.brand.get("past_performance", {}),
            "trend_report": trends or {},
            "month": month,
        })

    def _run_trends(self, strategy: dict | None = None) -> dict:
        return self.trend_agent.run({
            "brand_profile": self.brand,
            "strategy_plan": strategy or {},
        })

    def _run_campaign(self, strategy: dict, trends: dict, week: int) -> dict:
        return self.campaign_agent.run({
            "brand_profile": self.brand,
            "strategy_plan": strategy,
            "trend_report": trends,
            "week_number": week,
        })

    def _run_content_block(
        self, campaign: dict, strategy: dict, trends: dict
    ) -> list[dict]:
        posts = campaign.get("posts", [])
        packages = []

        # Filter to feed posts (not stories — those don't need full packages)
        feed_posts = [p for p in posts if p.get("type") != "story"]

        for post in feed_posts:
            post_type = (post.get("type") or "post").lower()

            # Get available photos for image posts
            available_photos = None
            if post_type == "image":
                available_photos = self.store.get_available_product_indices(self.brand)

            # Content (caption, hashtags)
            content = self.content_agent.run({
                "post_brief": post,
                "brand_profile": self.brand,
                "strategy_plan": strategy,
                "available_photo_indices": available_photos,
            })

            # Track the used photo
            selected_idx = content.get("selected_product_idx")
            if selected_idx is not None:
                self.store.save_used_image(int(selected_idx), post["id"])

            self.store.save_content(content, post["id"])

            # Visual direction
            visual = self.visual_agent.run({
                "post_brief": post,
                "content_package": content,
                "brand_profile": self.brand,
            })
            self.store.save_visual(visual, post["id"])

            # Reel production package (only for reels)
            reel = self.reel_agent.run({
                "post_brief": post,
                "content_package": content,
                "brand_profile": self.brand,
                "trend_report": trends,
            })
            if not reel.get("skipped"):
                self.store.save_reel(reel, post["id"])

            packages.append({
                "post_id": post["id"],
                "post_type": post.get("type"),
                **content,
                "visual": visual,
                "reel": reel if not reel.get("skipped") else None,
            })

        return packages

    def _run_engagement(self) -> dict:
        return self.engagement_agent.run({
            "brand_profile": self.brand,
        })

    def _run_scheduling(self, campaign: dict, content_packages: list) -> dict:
        return self.scheduler_agent.run({
            "campaign_plan": campaign,
            "content_packages": content_packages,
            "brand_profile": self.brand,
        })

    def _run_analytics(self, campaign: dict) -> dict:
        return self.analytics_agent.run({
            "brand_profile": self.brand,
            "campaign_plan": campaign,
            "published_posts": [],
            "period": "weekly",
        })

    def _run_optimization(
        self, analytics: dict, strategy: dict, campaign: dict
    ) -> dict:
        return self.optimization_agent.run({
            "brand_profile": self.brand,
            "analytics_report": analytics,
            "strategy_plan": strategy,
            "campaign_plan": campaign,
        })

    # ══════════════════════════════════════════════════════════════════════════
    # PRIVATE: Rich display helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _run_phase(self, title: str, subtitle: str, fn) -> dict:
        """Wrap a phase call with nice headers and timing."""
        self.console.print()
        self.console.rule(f"[bold cyan]{title}[/bold cyan]  [dim]{subtitle}[/dim]")
        start = time.time()
        result = fn()
        elapsed = time.time() - start
        self.console.print(
            f"  [dim]✓ Completed in {elapsed:.1f}s[/dim]"
        )
        return result

    def _print_cycle_header(self, week: int) -> None:
        self.console.print()
        self.console.print(
            Panel(
                f"[bold white]AI Social Media OS[/bold white]  ·  "
                f"[cyan]{self.brand.get('name', 'Brand')}[/cyan]  ·  "
                f"[green]Week {week}[/green]  ·  "
                f"[yellow]Mode: {RUN_MODE.upper()}[/yellow]\n"
                f"[dim]{datetime.now().strftime('%A, %d %B %Y  %H:%M')}[/dim]",
                border_style="bold blue",
                expand=False,
            )
        )

    def _print_block_header(self, letter: str, name: str, icon: str) -> None:
        self.console.print()
        self.console.print(
            Panel(
                f"[bold]{icon}  Block {letter}: {name}[/bold]",
                border_style="cyan",
                expand=False,
            )
        )

    def _print_cycle_summary(self, results: dict) -> None:
        self.console.print()
        self.console.rule("[bold green]✅  CYCLE COMPLETE[/bold green]")
        self.console.print()

        table = Table(title=f"Weekly Summary — {self.brand.get('name')}", show_header=True)
        table.add_column("Phase", style="bold cyan")
        table.add_column("Output", style="green")
        table.add_column("Status", style="bold")

        strategy = results.get("strategy", {})
        campaign = results.get("campaign", {})
        analytics = results.get("analytics", {})
        engagement = results.get("engagement", {})
        optimizations = results.get("optimizations", {})

        rows = [
            ("Strategy", f"{len(strategy.get('campaign_themes', []))} campaign themes", "✅"),
            ("Trends", f"{len(results.get('trends', {}).get('trending_topics', []))} topics found", "✅"),
            ("Campaign", f"{campaign.get('weekly_summary', {}).get('total_posts', 0)} posts planned", "✅"),
            ("Content", f"{len(results.get('content_packages', []))} packages generated", "✅"),
            ("Engagement", f"{engagement.get('summary', {}).get('hot_leads_found', 0)} hot leads", "✅"),
            ("Schedule", f"{results.get('schedule', {}).get('publishing_manifest', {}).get('total_posts', 0)} posts queued", "✅"),
            ("Analytics", f"Engagement: {analytics.get('content_performance', {}).get('avg_engagement_rate', '?')}%", "✅"),
            ("Optimization", f"{len(optimizations.get('quick_wins', []))} quick wins", "✅"),
        ]
        for r in rows:
            table.add_row(*r)

        self.console.print(table)
        self.console.print()

        # Key numbers
        followers_gained = analytics.get("account_metrics", {}).get("followers_gained", 0)
        hot_leads = engagement.get("summary", {}).get("hot_leads_found", 0)
        next_priorities = optimizations.get("next_week_priorities", [])

        self.console.print(Panel(
            f"[bold green]Followers gained this week:[/bold green] +{followers_gained}\n"
            f"[bold yellow]Hot leads identified:[/bold yellow] {hot_leads}\n"
            f"[bold cyan]Next week's #1 priority:[/bold cyan] {next_priorities[0] if next_priorities else 'See optimization report'}",
            title="Key Metrics",
            border_style="green",
        ))
        self.console.print()
