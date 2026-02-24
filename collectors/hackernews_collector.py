from __future__ import annotations

"""
Hacker News collector — searches HN stories and comments via Algolia API.
No authentication required, completely free.
"""

import logging
import requests

import db

log = logging.getLogger(__name__)

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def collect_posts(keywords: list[str], limit: int = 50, search_type: str = "story") -> dict:
    """
    Collect Hacker News posts matching frustration keywords.

    Args:
        keywords:     List of frustration keywords to search
        limit:        Max items to fetch per keyword batch
        search_type:  'story', 'comment', or 'all'
    """
    stats = {
        "platform": "hackernews",
        "source": "algolia",
        "items_fetched": 0,
        "posts_inserted": 0,
        "duplicates_skipped": 0,
        "filtered_out": 0,
    }

    # Build search query from keywords (OR logic)
    query = " OR ".join(f'"{kw}"' for kw in keywords[:10])

    tags = ""
    if search_type == "story":
        tags = "story"
    elif search_type == "comment":
        tags = "comment"
    # 'all' = no tag filter

    params = {
        "query": query,
        "hitsPerPage": min(limit, 100),
        "tags": tags,
    }
    if not tags:
        del params["tags"]

    try:
        resp = requests.get(ALGOLIA_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("hits", [])
    except Exception as e:
        log.error("Hacker News API error: %s", e)
        stats["error"] = str(e)
        return stats

    stats["items_fetched"] = len(hits)

    for hit in hits:
        # Build post from HN data
        title = hit.get("title") or ""
        comment_text = hit.get("comment_text") or hit.get("story_text") or ""
        author = hit.get("author") or ""
        object_id = hit.get("objectID") or ""
        points = hit.get("points") or 0

        # Build URL
        if hit.get("url"):
            url = hit["url"]
        else:
            url = f"https://news.ycombinator.com/item?id={object_id}"

        full_text = f"{title} {comment_text}"

        if not full_text.strip():
            stats["filtered_out"] += 1
            continue

        if keywords and not _matches_keywords(full_text, keywords):
            stats["filtered_out"] += 1
            continue

        post_data = {
            "platform": "hackernews",
            "title": title[:500] if title else "",
            "content": comment_text[:2000] if comment_text else title[:2000],
            "author": author,
            "url": url,
            "score": points,
            "subreddit": "",  # Not applicable
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
                log.error("Error inserting HN post: %s", e)

    log.info("HN: %d hits → %d inserted, %d dups, %d filtered",
             stats["items_fetched"], stats["posts_inserted"],
             stats["duplicates_skipped"], stats["filtered_out"])

    return stats
