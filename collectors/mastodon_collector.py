from __future__ import annotations

"""
Mastodon collector — reads public timeline and hashtag feeds.
No authentication required for public posts.
"""

import logging
import requests

import db

log = logging.getLogger(__name__)

DEFAULT_INSTANCES = ["mastodon.social", "fosstodon.org", "techhub.social"]


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def _strip_html(html: str) -> str:
    """Basic HTML tag stripping for Mastodon post content."""
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def collect_posts(
    keywords: list[str],
    instances: list[str] | None = None,
    limit: int = 40,
) -> dict:
    """
    Collect Mastodon posts from public timelines of specified instances.

    For each instance, fetches the public timeline and filters by keywords.
    """
    instances = instances or DEFAULT_INSTANCES

    stats = {
        "platform": "mastodon",
        "source": "public_api",
        "items_fetched": 0,
        "posts_inserted": 0,
        "duplicates_skipped": 0,
        "filtered_out": 0,
    }

    for instance in instances:
        try:
            _collect_from_instance(instance, keywords, limit, stats)
        except Exception as e:
            log.error("Error collecting from %s: %s", instance, e)

    log.info("Mastodon: %d fetched → %d inserted, %d dups, %d filtered",
             stats["items_fetched"], stats["posts_inserted"],
             stats["duplicates_skipped"], stats["filtered_out"])

    return stats


def _collect_from_instance(
    instance: str, keywords: list[str], limit: int, stats: dict
) -> None:
    """Fetch public timeline from a single Mastodon instance."""
    url = f"https://{instance}/api/v1/timelines/public"
    params = {"limit": min(limit, 40), "local": "false"}

    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 401:
            log.warning("Instance %s requires auth for public timeline — skipping", instance)
            return
        resp.raise_for_status()
        statuses = resp.json()
    except requests.exceptions.RequestException as e:
        log.warning("Failed to reach %s: %s", instance, e)
        return

    stats["items_fetched"] += len(statuses)

    for status in statuses:
        raw_content = status.get("content", "")
        text = _strip_html(raw_content)

        if not text:
            stats["filtered_out"] += 1
            continue

        if keywords and not _matches_keywords(text, keywords):
            stats["filtered_out"] += 1
            continue

        acct = status.get("account", {})
        author = acct.get("acct") or acct.get("username") or ""

        post_data = {
            "platform": "mastodon",
            "title": "",
            "content": text[:2000],
            "author": f"{author}@{instance}" if author else "",
            "url": status.get("url") or status.get("uri") or "",
            "score": (status.get("favourites_count") or 0) + (status.get("reblogs_count") or 0),
            "subreddit": instance,  # Store instance name in subreddit field
        }

        try:
            result = db.insert_raw_post(post_data)
            if result:
                stats["posts_inserted"] += 1
            else:
                stats["duplicates_skipped"] += 1
        except Exception as e:
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                stats["duplicates_skipped"] += 1
            else:
                log.error("Error inserting Mastodon post: %s", e)
