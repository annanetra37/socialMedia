#!/usr/bin/env python3
"""
AI Social Media Operating System — Main Entry Point

Usage:
    python main.py                          # Full cycle (demo mode, example brand)
    python main.py --cycle full             # Full cycle
    python main.py --cycle monitoring       # Block A: Monitoring only
    python main.py --cycle engagement       # Block B: Engagement only
    python main.py --cycle content          # Block C: Content only
    python main.py --cycle growth           # Block D: Growth only
    python main.py --week 2                 # Run for week 2
    python main.py --brand custom.json      # Use custom brand profile
    python main.py --show results           # Show last run's stored results
    python main.py --pipeline              # Show the agent pipeline diagram
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel

# ── Make sure imports work from any working directory ──────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import ANTHROPIC_API_KEY, RUN_MODE
from dashboard.cli_dashboard import Dashboard
from orchestrator.orchestrator import Orchestrator
from storage.data_store import DataStore


def load_brand_profile(path: Optional[str] = None) -> dict:
    """Load brand profile from a JSON file or fall back to the example."""
    if path:
        profile_path = Path(path)
        if not profile_path.exists():
            console = Console()
            console.print(f"[red]Brand profile not found: {path}[/red]")
            sys.exit(1)
        with profile_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    # Default: example brand
    default = Path(__file__).parent / "config" / "brand_profiles" / "example_brand.json"
    with default.open("r", encoding="utf-8") as f:
        return json.load(f)


def check_api_key(console: Console) -> None:
    """Warn if no API key is set and we're in live mode."""
    if RUN_MODE == "live" and not ANTHROPIC_API_KEY:
        console.print(Panel(
            "[bold red]⚠️  ANTHROPIC_API_KEY is not set.[/bold red]\n\n"
            "Copy .env.example to .env and add your key, or run in demo mode:\n"
            "[cyan]  RUN_MODE=demo python main.py[/cyan]",
            border_style="red",
        ))
        sys.exit(1)

    if RUN_MODE == "demo":
        console.print(
            "[yellow]⚠  Running in DEMO mode — no real API calls, no Instagram publishing.[/yellow]\n"
            "[dim]Set RUN_MODE=live in .env for live operation.[/dim]\n"
        )


def run_cycle(args: argparse.Namespace) -> None:
    console = Console()
    check_api_key(console)

    brand = load_brand_profile(args.brand)
    dashboard = Dashboard(console)
    dashboard.show_welcome(brand["name"], RUN_MODE)
    dashboard.show_agent_pipeline()

    orch = Orchestrator(brand)
    week = getattr(args, "week", 1)
    cycle = getattr(args, "cycle", "full")

    if cycle == "full" or cycle is None:
        results = orch.run_full_cycle(week_number=week)
        _display_full_results(dashboard, results)

    elif cycle == "monitoring":
        results = orch.run_monitoring_block()
        dashboard.show_trend_summary(results.get("trends", {}))
        dashboard.show_analytics_summary(results.get("analytics", {}))

    elif cycle == "engagement":
        results = orch.run_engagement_block()
        dashboard.show_engagement_summary(results)

    elif cycle == "content":
        results = orch.run_content_block(week=week)
        campaign = results.get("campaign", {})
        dashboard.show_campaign_summary(campaign)
        for pkg in results.get("content_packages", []):
            dashboard.show_content_summary(pkg)

    elif cycle == "growth":
        results = orch.run_growth_block(week=week)
        dashboard.show_schedule(results.get("schedule", {}))
        dashboard.show_optimization_summary(results.get("optimizations", {}))

    else:
        console.print(f"[red]Unknown cycle: {cycle}[/red]")
        sys.exit(1)


def show_results(args: argparse.Namespace) -> None:
    """Display stored results from the last run without re-running agents."""
    console = Console()
    brand = load_brand_profile(getattr(args, "brand", None))
    store = DataStore(brand["name"])
    dashboard = Dashboard(console)

    dashboard.show_welcome(brand["name"], RUN_MODE)

    strategy = store.load_strategy()
    if strategy:
        dashboard.show_strategy_summary(strategy)

    trends = store.load_trend_report()
    if trends:
        dashboard.show_trend_summary(trends)

    campaign = store.load_campaign(week=getattr(args, "week", 1))
    if campaign:
        dashboard.show_campaign_summary(campaign)

    analytics = store.load_latest_analytics()
    if analytics:
        dashboard.show_analytics_summary(analytics)

    optimizations = store.load_latest_optimization()
    if optimizations:
        dashboard.show_optimization_summary(optimizations)

    dashboard.show_stored_data_browser(store)


def show_pipeline(_args: argparse.Namespace) -> None:
    console = Console()
    Dashboard(console).show_agent_pipeline()


def _display_full_results(dashboard: Dashboard, results: dict) -> None:
    dashboard.show_strategy_summary(results.get("strategy", {}))
    dashboard.show_trend_summary(results.get("trends", {}))
    dashboard.show_campaign_summary(results.get("campaign", {}))

    for pkg in results.get("content_packages", []):
        dashboard.show_content_summary(pkg)

    dashboard.show_engagement_summary(results.get("engagement", {}))
    dashboard.show_schedule(results.get("schedule", {}))
    dashboard.show_analytics_summary(results.get("analytics", {}))
    dashboard.show_optimization_summary(results.get("optimizations", {}))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ai-smos",
        description="AI Social Media Operating System — automates the full social media marketing cycle",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                          Run the full cycle in demo mode
  python main.py --cycle full --week 2   Full cycle for week 2
  python main.py --cycle monitoring      Run monitoring block only
  python main.py --cycle engagement      Process comments & DMs
  python main.py --cycle content         Generate content for the week
  python main.py --cycle growth          Schedule posts + get optimizations
  python main.py --show results          Display last run's results
  python main.py --pipeline              Show the 9-agent pipeline
  python main.py --brand my_brand.json   Use a custom brand profile
        """,
    )

    parser.add_argument(
        "--cycle",
        choices=["full", "monitoring", "engagement", "content", "growth"],
        default="full",
        help="Which cycle to run (default: full)",
    )
    parser.add_argument(
        "--week",
        type=int,
        choices=[1, 2, 3, 4],
        default=1,
        help="Week number within the month (1-4, default: 1)",
    )
    parser.add_argument(
        "--brand",
        type=str,
        default=None,
        help="Path to a custom brand profile JSON file",
    )
    parser.add_argument(
        "--show",
        choices=["results"],
        default=None,
        help="Display stored results without running agents",
    )
    parser.add_argument(
        "--pipeline",
        action="store_true",
        help="Show the agent pipeline diagram and exit",
    )

    args = parser.parse_args()

    if args.pipeline:
        show_pipeline(args)
        return

    if args.show == "results":
        show_results(args)
        return

    run_cycle(args)


if __name__ == "__main__":
    main()
