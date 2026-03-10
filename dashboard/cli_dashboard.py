"""
CLI Dashboard — Rich-powered terminal UI for the AI Social Media OS.

Provides:
- Live run visualisation (progress, agent outputs)
- Post-run summary tables
- Analytics display
- Stored data browser
"""

import json
from datetime import datetime
from typing import Any, Optional

from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box


class Dashboard:
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    # ── Full-page views ────────────────────────────────────────────────────────

    def show_welcome(self, brand_name: str, mode: str) -> None:
        """Display the welcome/startup screen."""
        self.console.clear()
        banner = """
  ╔═══════════════════════════════════════════════════════════════╗
  ║          AI SOCIAL MEDIA OPERATING SYSTEM                     ║
  ║          Powered by Claude claude-opus-4-6                         ║
  ╚═══════════════════════════════════════════════════════════════╝"""

        self.console.print(Text(banner, style="bold blue"))
        self.console.print()
        self.console.print(
            Panel(
                f"  Brand:   [bold cyan]{brand_name}[/bold cyan]\n"
                f"  Mode:    [bold {'green' if mode == 'live' else 'yellow'}]{mode.upper()}[/bold {'green' if mode == 'live' else 'yellow'}]\n"
                f"  Started: [dim]{datetime.now().strftime('%A, %d %B %Y  %H:%M')}[/dim]",
                border_style="blue",
                expand=False,
            )
        )
        self.console.print()

    def show_agent_pipeline(self) -> None:
        """Display the 9-agent pipeline diagram."""
        pipeline = """
  ┌────────────────────────────────────────────────────────────┐
  │  1. Strategy Agent      ──►  Monthly strategy + pillars    │
  │  2. Trend Research      ──►  Viral formats + hashtags      │
  │  3. Campaign Planner    ──►  Weekly posting calendar       │
  │                         ──►  (parallel generation)         │
  │  4. Content Agent       ──►  Captions + hashtags + CTAs    │
  │  5. Visual Agent        ──►  Image prompts + design specs  │
  │  6. Reel Agent          ──►  Video scripts + shot list     │
  │  7. Engagement Agent    ──►  Comment/DM replies + leads    │
  │  8. Scheduler Agent     ──►  Publishing via Instagram API  │
  │  9. Analytics Agent     ──►  Performance metrics           │
  │ 10. Optimization Agent  ──►  Improvements → back to #1     │
  └────────────────────────────────────────────────────────────┘"""
        self.console.print(Panel(pipeline, title="Agent Pipeline", border_style="cyan"))
        self.console.print()

    # ── Summary tables ─────────────────────────────────────────────────────────

    def show_strategy_summary(self, strategy: dict) -> None:
        """Display strategy plan in a rich table."""
        self.console.print()
        self.console.rule("[bold blue]📋 Strategy Summary[/bold blue]")

        # Content pillars
        pillars = strategy.get("content_pillars", [])
        if pillars:
            table = Table(title="Content Pillars", box=box.ROUNDED, show_header=True)
            table.add_column("Pillar", style="bold cyan")
            table.add_column("Mix %", justify="right", style="green")
            table.add_column("Rationale", style="dim")
            for p in pillars:
                table.add_row(p["name"], f"{p['percentage']}%", p.get("rationale", ""))
            self.console.print(table)

        # Campaign themes
        themes = strategy.get("campaign_themes", [])
        if themes:
            table2 = Table(title="Weekly Campaign Themes", box=box.ROUNDED)
            table2.add_column("Week", justify="center")
            table2.add_column("Theme", style="bold yellow")
            table2.add_column("Emotion", style="magenta")
            table2.add_column("Hook Style", style="dim")
            for t in themes:
                table2.add_row(str(t["week"]), t["theme"], t.get("emotion", ""), t.get("hook_style", ""))
            self.console.print(table2)

        # KPIs
        kpis = strategy.get("kpis", {})
        if kpis:
            kpi_text = (
                f"[bold]Followers target:[/bold] +{kpis.get('followers_target', '?')}/month  |  "
                f"[bold]Engagement target:[/bold] {kpis.get('engagement_rate_target', '?')}%  |  "
                f"[bold]DM leads target:[/bold] {kpis.get('dm_leads_target', '?')}"
            )
            self.console.print(Panel(kpi_text, title="KPIs", border_style="green"))

    def show_trend_summary(self, trends: dict) -> None:
        """Display trend report summary."""
        self.console.print()
        self.console.rule("[bold magenta]🔍 Trend Report[/bold magenta]")

        topics = trends.get("trending_topics", [])
        if topics:
            table = Table(title="Trending Topics", box=box.ROUNDED)
            table.add_column("Topic", style="bold")
            table.add_column("Platform", style="cyan")
            table.add_column("Fit", justify="center", style="green")
            table.add_column("Urgency", style="yellow")
            table.add_column("Angle", style="dim")
            for t in topics:
                table.add_row(
                    t["topic"],
                    t.get("platform", ""),
                    f"{t.get('fit_score', '?')}/10",
                    t.get("urgency", ""),
                    t.get("content_angle", "")[:50],
                )
            self.console.print(table)

        recs = trends.get("top_recommendations", [])
        if recs:
            recs_text = "\n".join(f"  • {r}" for r in recs)
            self.console.print(Panel(recs_text, title="Top Recommendations", border_style="magenta"))

    def show_campaign_summary(self, campaign: dict) -> None:
        """Display the weekly posting calendar."""
        self.console.print()
        self.console.rule("[bold green]📅 Week's Posting Calendar[/bold green]")

        posts = campaign.get("posts", [])
        if not posts:
            self.console.print("[dim]No posts found.[/dim]")
            return

        table = Table(
            title=f"Week {campaign.get('week_number', '?')} — {campaign.get('theme', '')}",
            box=box.ROUNDED,
        )
        table.add_column("Day", style="bold")
        table.add_column("Time", justify="center")
        table.add_column("Type", style="cyan", justify="center")
        table.add_column("Priority", justify="center")
        table.add_column("Hook", style="yellow")
        table.add_column("CTA", style="dim")

        type_colors = {"reel": "red", "carousel": "blue", "image": "green", "story": "magenta"}
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}

        for post in posts:
            ptype = post.get("type", "?")
            color = type_colors.get(ptype, "white")
            priority = post.get("priority", "medium")
            table.add_row(
                post.get("day", ""),
                post.get("time", ""),
                f"[{color}]{ptype.upper()}[/{color}]",
                priority_icons.get(priority, ""),
                (post.get("hook", "")[:45] + "…") if len(post.get("hook", "")) > 45 else post.get("hook", ""),
                (post.get("cta", "")[:40] + "…") if len(post.get("cta", "")) > 40 else post.get("cta", ""),
            )
        self.console.print(table)

        summary = campaign.get("weekly_summary", {})
        if summary:
            self.console.print(
                f"  [bold]Total:[/bold] {summary.get('total_posts', 0)} posts  "
                f"([red]{summary.get('reels', 0)} reels[/red]  "
                f"[blue]{summary.get('carousels', 0)} carousels[/blue]  "
                f"[green]{summary.get('images', 0)} images[/green]  "
                f"[magenta]{summary.get('stories', 0)} stories[/magenta])"
            )

    def show_content_summary(self, content_package: dict) -> None:
        """Display a single post's content package."""
        post_id = content_package.get("post_id", "?")
        self.console.print()
        self.console.print(Panel(
            f"[bold]Post:[/bold] {post_id}  |  [bold]Type:[/bold] {content_package.get('post_type', '?').upper()}",
            border_style="yellow",
            expand=False,
        ))

        caption = content_package.get("caption", {})
        if caption:
            self.console.print(Panel(
                f"[bold]Hook:[/bold] {caption.get('hook', '')}\n\n"
                f"{caption.get('body', '')}\n\n"
                f"[bold]CTA:[/bold] {caption.get('cta', '')}",
                title="Caption",
                border_style="yellow",
            ))

        hashtags = content_package.get("hashtags", {})
        if hashtags:
            self.console.print(f"  [dim]{hashtags.get('full_set', '')}[/dim]")

    def show_engagement_summary(self, engagement: dict) -> None:
        """Display engagement processing summary."""
        self.console.print()
        self.console.rule("[bold green]💬 Engagement Report[/bold green]")

        # Hot leads
        leads = engagement.get("hot_leads", [])
        if leads:
            table = Table(title="🔥 Hot Leads", box=box.ROUNDED)
            table.add_column("Username", style="bold red")
            table.add_column("Source", style="cyan")
            table.add_column("Signal", style="yellow")
            table.add_column("Next Action", style="green")
            for lead in leads:
                table.add_row(
                    lead.get("username", ""),
                    lead.get("source", ""),
                    lead.get("signal", "")[:50],
                    lead.get("recommended_action", "")[:50],
                )
            self.console.print(table)

        # Summary stats
        summary = engagement.get("summary", {})
        if summary:
            self.console.print(
                f"  Comments processed: [bold]{summary.get('comments_processed', 0)}[/bold]  "
                f"| DMs processed: [bold]{summary.get('dms_processed', 0)}[/bold]  "
                f"| Hot leads: [bold red]{summary.get('hot_leads_found', 0)}[/bold red]"
            )

        # Proactive actions
        proactive = engagement.get("proactive_actions", [])
        if proactive:
            text = "\n".join(f"  • {a}" for a in proactive)
            self.console.print(Panel(text, title="Proactive Growth Actions", border_style="green"))

    def show_analytics_summary(self, analytics: dict) -> None:
        """Display analytics dashboard."""
        self.console.print()
        self.console.rule("[bold magenta]📊 Analytics Dashboard[/bold magenta]")

        metrics = analytics.get("account_metrics", {})
        if metrics:
            self.console.print(Panel(
                f"  [bold]Followers gained:[/bold] [green]+{metrics.get('followers_gained', 0)}[/green] "
                f"({metrics.get('follower_growth_rate', '?')})\n"
                f"  [bold]Total reach:[/bold] {metrics.get('total_reach', 0):,}\n"
                f"  [bold]Profile visits:[/bold] {metrics.get('profile_visits', 0):,}\n"
                f"  [bold]Website clicks:[/bold] {metrics.get('website_clicks', 0):,}",
                title="Account Metrics",
                border_style="magenta",
            ))

        content_perf = analytics.get("content_performance", {})
        breakdown = analytics.get("content_type_breakdown", {})
        if breakdown:
            table = Table(title="Content Type Performance", box=box.ROUNDED)
            table.add_column("Type", style="bold")
            table.add_column("Posts", justify="right")
            table.add_column("Avg Engagement", justify="right", style="green")
            table.add_column("Avg Reach", justify="right", style="cyan")
            for ctype, data in breakdown.items():
                if isinstance(data, dict):
                    table.add_row(
                        ctype.upper(),
                        str(data.get("posts", data.get("stories", "?"))),
                        f"{data.get('avg_engagement', data.get('avg_views', '?'))}%",
                        str(data.get("avg_reach", data.get("avg_views", "-"))),
                    )
            self.console.print(table)

        insights = analytics.get("key_insights", [])
        if insights:
            text = "\n".join(f"  💡 {i}" for i in insights)
            self.console.print(Panel(text, title="Key Insights", border_style="cyan"))

    def show_optimization_summary(self, optimizations: dict) -> None:
        """Display optimization recommendations."""
        self.console.print()
        self.console.rule("[bold red]⚙️  Optimization Recommendations[/bold red]")

        verdict = optimizations.get("performance_verdict", "?")
        verdict_color = {"excellent": "green", "good": "cyan", "average": "yellow", "poor": "red"}.get(verdict, "white")
        self.console.print(f"  Performance verdict: [bold {verdict_color}]{verdict.upper()}[/bold {verdict_color}]")

        # Quick wins
        wins = optimizations.get("quick_wins", [])
        if wins:
            table = Table(title="Quick Wins", box=box.ROUNDED)
            table.add_column("Action", style="bold green")
            table.add_column("Impact", style="yellow")
            table.add_column("Effort", justify="center")
            table.add_column("Timeline", style="cyan")
            for w in wins:
                effort_color = {"low": "green", "medium": "yellow", "high": "red"}.get(w.get("effort", ""), "white")
                table.add_row(
                    w.get("action", "")[:55],
                    w.get("expected_impact", "")[:40],
                    f"[{effort_color}]{w.get('effort', '?').upper()}[/{effort_color}]",
                    w.get("timeline", "").replace("_", " "),
                )
            self.console.print(table)

        # Content mix update
        mix_update = optimizations.get("content_mix_update", {})
        if mix_update:
            current = mix_update.get("current", {})
            recommended = mix_update.get("recommended", {})
            if current and recommended:
                self.console.print(Panel(
                    "\n".join(
                        f"  {k}: [dim]{int(v*100)}%[/dim] → [bold green]{int(recommended.get(k, v)*100)}%[/bold green]"
                        for k, v in current.items()
                    ),
                    title="Content Mix Update",
                    border_style="red",
                ))

        # Next week priorities
        priorities = optimizations.get("next_week_priorities", [])
        if priorities:
            text = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(priorities))
            self.console.print(Panel(text, title="Next Week's Priorities", border_style="green"))

    def show_schedule(self, schedule: dict) -> None:
        """Display the publishing schedule."""
        self.console.print()
        self.console.rule("[bold white]🗓️  Publishing Schedule[/bold white]")

        posts = schedule.get("scheduled_posts", [])
        if not posts:
            self.console.print("[dim]No posts scheduled.[/dim]")
            return

        table = Table(title="Publishing Queue", box=box.ROUNDED)
        table.add_column("Post ID", style="dim")
        table.add_column("Day", style="bold")
        table.add_column("Scheduled (UTC)", style="cyan")
        table.add_column("Type", justify="center")
        table.add_column("Status", justify="center")
        table.add_column("Caption Preview", style="dim")

        for p in posts:
            dt = p.get("scheduled_datetime_utc", "")[:16].replace("T", " ")
            status = p.get("status", "?")
            status_style = "green" if status == "published" else ("yellow" if status == "scheduled" else "dim")
            table.add_row(
                p.get("post_id", ""),
                p.get("day", ""),
                dt,
                p.get("post_type", "").upper(),
                f"[{status_style}]{status}[/{status_style}]",
                (p.get("caption_preview", "")[:40] + "…") if len(p.get("caption_preview", "")) > 40 else p.get("caption_preview", ""),
            )
        self.console.print(table)

        manifest = schedule.get("publishing_manifest", {})
        if manifest:
            self.console.print(
                f"  Total: [bold]{manifest.get('total_posts', 0)}[/bold] posts  |  "
                f"Feed: [bold]{manifest.get('this_week_feed_posts', 0)}[/bold]  |  "
                f"Stories: [bold]{manifest.get('this_week_stories', 0)}[/bold]"
            )

    def show_stored_data_browser(self, data_store) -> None:
        """Show what's currently stored for this brand."""
        self.console.print()
        self.console.rule("[bold]📁 Stored Data Browser[/bold]")
        summary = data_store.get_session_summary()

        table = Table(title="Data Store Contents", box=box.ROUNDED)
        table.add_column("Category", style="bold cyan")
        table.add_column("Files", style="green")
        table.add_column("Latest File", style="dim")

        for category in ["strategy", "trends", "campaigns", "content", "analytics", "optimizations"]:
            files = summary.get(f"{category}_files", [])
            latest = files[-1] if files else "—"
            table.add_row(category, str(len(files)), latest)

        self.console.print(table)
