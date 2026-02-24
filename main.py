"""
Main entry point — CLI for collect, analyze, and dashboard commands.
"""

import sys
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("social_listener")

PLATFORMS = ["reddit", "hackernews", "mastodon", "devto", "apify"]


def cmd_collect(args):
    """Run collectors for all configured platforms."""
    import db

    settings = db.get_settings()
    keywords_raw = settings.get("frustration_keywords", "")
    keywords = [kw.strip() for kw in keywords_raw.split(",") if kw.strip()]
    subreddits_raw = settings.get("subreddits", "")
    subreddits = [s.strip() for s in subreddits_raw.split(",") if s.strip()]
    limit = args.limit
    target = args.platform  # None = all

    all_stats = []

    # ── Reddit (PRAW) ─────────────────────────
    if target in (None, "reddit"):
        try:
            from collectors.reddit_collector import collect_posts, is_configured as reddit_ok
            if reddit_ok():
                logger.info("🔍 Collecting from Reddit (PRAW)...")
                stats = collect_posts(limit_per_sub=limit)
                all_stats.append({"platform": "reddit", "source": "praw", **stats})
            else:
                logger.info("⏭️  Reddit PRAW not configured — skipping")
        except Exception as e:
            logger.error(f"Reddit PRAW error: {e}")

    # ── Apify platforms (Reddit, Twitter, LinkedIn, Facebook, Instagram) ──
    if target in (None, "apify"):
        try:
            from collectors import apify_collector
            logger.info("🔍 Collecting via Apify actors...")
            apify_results = apify_collector.collect_all(keywords, subreddits, limit)
            all_stats.extend(apify_results)
        except Exception as e:
            logger.error(f"Apify collector error: {e}")

    # ── Hacker News ───────────────────────────
    if target in (None, "hackernews"):
        try:
            from collectors import hackernews_collector
            logger.info("🔍 Collecting from Hacker News...")
            stats = hackernews_collector.collect_posts(keywords, limit=limit)
            all_stats.append(stats)
        except Exception as e:
            logger.error(f"HN collector error: {e}")

    # ── Mastodon ──────────────────────────────
    if target in (None, "mastodon"):
        try:
            from collectors import mastodon_collector
            instances_raw = settings.get("mastodon_instances", "mastodon.social")
            instances = [i.strip() for i in instances_raw.split(",") if i.strip()]
            logger.info("🔍 Collecting from Mastodon...")
            stats = mastodon_collector.collect_posts(keywords, instances=instances, limit=limit)
            all_stats.append(stats)
        except Exception as e:
            logger.error(f"Mastodon collector error: {e}")

    # ── Dev.to ────────────────────────────────
    if target in (None, "devto"):
        try:
            from collectors import devto_collector
            logger.info("🔍 Collecting from Dev.to...")
            stats = devto_collector.collect_posts(keywords, limit=limit)
            all_stats.append(stats)
        except Exception as e:
            logger.error(f"Dev.to collector error: {e}")

    logger.info("✅ Collection complete across %d platforms", len(all_stats))
    for s in all_stats:
        p = s.get("platform", "?")
        ins = s.get("posts_inserted", 0)
        logger.info(f"   {p}: {ins} new posts")

    return all_stats


def cmd_analyze(args):
    """Run the analysis pipeline."""
    from analysis.pipeline import run_pipeline
    logger.info("🧠 Starting analysis pipeline...")
    stats = run_pipeline(limit=args.limit)
    logger.info(f"✅ Analysis done: {stats}")


def cmd_dashboard(args):
    """Start the web dashboard."""
    from dashboard.app import create_app
    from config import FLASK_PORT, FLASK_DEBUG

    app = create_app()
    port = args.port or FLASK_PORT
    logger.info(f"🚀 Starting dashboard on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=args.debug or FLASK_DEBUG)


def main():
    parser = argparse.ArgumentParser(
        description="AI-Powered Social Listening & Outreach System"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # collect
    collect_parser = subparsers.add_parser("collect", help="Collect posts from all platforms")
    collect_parser.add_argument("--limit", type=int, default=25, help="Posts per source (default: 25)")
    collect_parser.add_argument("--platform", choices=PLATFORMS, default=None,
                               help="Only collect from this platform")
    collect_parser.set_defaults(func=cmd_collect)

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Run analysis pipeline")
    analyze_parser.add_argument("--limit", type=int, default=50, help="Max posts to analyze (default: 50)")
    analyze_parser.set_defaults(func=cmd_analyze)

    # dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Start web dashboard")
    dash_parser.add_argument("--port", type=int, default=None, help="Port (default: from .env or 5000)")
    dash_parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    dash_parser.set_defaults(func=cmd_dashboard)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
