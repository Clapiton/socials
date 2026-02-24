from __future__ import annotations

"""
Reddit collector — polls subreddits for new posts matching frustration keywords.
"""

import logging
from datetime import datetime, timezone
import praw
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
import db

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    """Check if Reddit API credentials are available."""
    return bool(REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET)


def create_reddit_client() -> praw.Reddit:
    """Create and return a PRAW Reddit client."""
    if not is_configured():
        raise ValueError("REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET must be set in .env")
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )


def get_frustration_keywords() -> list[str]:
    """Fetch frustration keywords from settings."""
    settings = db.get_settings()
    raw = settings.get("frustration_keywords", "")
    return [kw.strip().lower() for kw in raw.split(",") if kw.strip()]


def get_subreddits() -> list[str]:
    """Fetch monitored subreddits from settings."""
    settings = db.get_settings()
    raw = settings.get("subreddits", "")
    return [s.strip() for s in raw.split(",") if s.strip()]


def matches_keywords(text: str, keywords: list[str]) -> bool:
    """Check if text contains any frustration keyword."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def collect_posts(limit_per_sub: int = 25) -> dict:
    """
    Poll all configured subreddits for new posts.
    Returns a summary dict with counts.
    """
    reddit = create_reddit_client()
    subreddits = get_subreddits()
    keywords = get_frustration_keywords()

    stats = {"subreddits_checked": 0, "posts_scanned": 0, "posts_matched": 0, "posts_inserted": 0, "duplicates_skipped": 0}

    if not subreddits:
        logger.warning("No subreddits configured. Add them in Settings.")
        return stats

    logger.info(f"Collecting from {len(subreddits)} subreddits: {', '.join(subreddits)}")
    logger.info(f"Using {len(keywords)} frustration keywords")

    for sub_name in subreddits:
        try:
            subreddit = reddit.subreddit(sub_name)
            stats["subreddits_checked"] += 1

            for submission in subreddit.new(limit=limit_per_sub):
                stats["posts_scanned"] += 1

                # Combine title and selftext for keyword matching
                full_text = f"{submission.title} {submission.selftext}"

                if not matches_keywords(full_text, keywords):
                    continue

                stats["posts_matched"] += 1

                # Build post data
                post_data = {
                    "platform": "reddit",
                    "post_id": submission.id,
                    "author": str(submission.author) if submission.author else "[deleted]",
                    "title": submission.title,
                    "content": submission.selftext or submission.title,
                    "url": f"https://reddit.com{submission.permalink}",
                    "subreddit": sub_name,
                    "score": submission.score,
                    "num_comments": submission.num_comments,
                    "created_at": datetime.fromtimestamp(submission.created_utc, tz=timezone.utc).isoformat(),
                }

                result = db.insert_raw_post(post_data)
                if result:
                    stats["posts_inserted"] += 1
                else:
                    stats["duplicates_skipped"] += 1

        except Exception as e:
            logger.error(f"Error collecting from r/{sub_name}: {e}")
            continue

    logger.info(
        f"Collection complete — Scanned: {stats['posts_scanned']}, "
        f"Matched: {stats['posts_matched']}, "
        f"Inserted: {stats['posts_inserted']}, "
        f"Duplicates: {stats['duplicates_skipped']}"
    )
    return stats
