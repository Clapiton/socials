from __future__ import annotations

"""
Dev.to collector — searches published articles via free public API.
No authentication required.
"""

import logging
import requests

import db

log = logging.getLogger(__name__)

DEVTO_URL = "https://dev.to/api/articles"


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def collect_posts(keywords: list[str], limit: int = 30) -> dict:
    """
    Collect Dev.to articles matching frustration keywords.
    Uses the free public articles endpoint with tag-based search.
    """
    stats = {
        "platform": "devto",
        "source": "public_api",
        "items_fetched": 0,
        "posts_inserted": 0,
        "duplicates_skipped": 0,
        "filtered_out": 0,
    }

    # Search for recent articles
    params = {
        "per_page": min(limit, 30),
        "state": "rising",
    }

    try:
        resp = requests.get(DEVTO_URL, params=params, timeout=15)
        resp.raise_for_status()
        articles = resp.json()
    except Exception as e:
        log.error("Dev.to API error: %s", e)
        stats["error"] = str(e)
        return stats

    stats["items_fetched"] = len(articles)

    for article in articles:
        title = article.get("title") or ""
        description = article.get("description") or ""
        full_text = f"{title} {description}"

        if not full_text.strip():
            stats["filtered_out"] += 1
            continue

        if keywords and not _matches_keywords(full_text, keywords):
            stats["filtered_out"] += 1
            continue

        tags = article.get("tag_list") or []
        user = article.get("user") or {}

        post_data = {
            "platform": "devto",
            "post_id": str(article.get("id", "")),
            "title": title[:500],
            "content": description[:2000],
            "author": user.get("username") or user.get("name") or "",
            "url": article.get("url") or "",
            "score": article.get("public_reactions_count") or 0,
            "subreddit": ", ".join(tags[:3]) if tags else "",
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
                log.error("Error inserting Dev.to post: %s", e)

    log.info("Dev.to: %d articles → %d inserted, %d dups, %d filtered",
             stats["items_fetched"], stats["posts_inserted"],
             stats["duplicates_skipped"], stats["filtered_out"])

    return stats
