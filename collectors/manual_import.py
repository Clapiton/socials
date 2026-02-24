from __future__ import annotations

"""
Manual import — parse raw text or CSV into raw_posts.
Used via the dashboard for testing the pipeline without any API keys.
"""

import csv
import io
import logging
from datetime import datetime, timezone

import db

log = logging.getLogger(__name__)


def import_text(text: str, author: str = "manual", source_label: str = "") -> dict:
    """
    Import raw text as a single post.

    Args:
        text:           The post content
        author:         Optional author name
        source_label:   Optional label (e.g. 'pasted from Reddit')
    """
    if not text.strip():
        return {"posts_inserted": 0, "error": "Empty text"}

    post_data = {
        "platform": "manual",
        "title": source_label or "Manual import",
        "content": text[:5000],
        "author": author,
        "url": "",
        "score": 0,
        "subreddit": source_label,
    }

    try:
        result = db.insert_raw_post(post_data)
        inserted = 1 if result else 0
    except Exception as e:
        log.error("Error inserting manual post: %s", e)
        return {"posts_inserted": 0, "error": str(e)}

    return {"platform": "manual", "posts_inserted": inserted}


def import_csv(csv_text: str) -> dict:
    """
    Import posts from CSV text.

    Expected columns (flexible — reads headers):
      - content (or text, body, post)  — required
      - title                          — optional
      - author (or user, username)     — optional
      - url (or link)                  — optional
      - platform                       — optional, defaults to 'manual'
      - subreddit (or source, group)   — optional
    """
    stats = {"platform": "manual", "posts_inserted": 0, "rows_parsed": 0, "errors": 0}

    reader = csv.DictReader(io.StringIO(csv_text))

    if not reader.fieldnames:
        stats["error"] = "Could not parse CSV headers"
        return stats

    # Flexible column mapping
    headers = {h.lower().strip(): h for h in reader.fieldnames}
    content_col = _find_col(headers, ["content", "text", "body", "post", "message"])
    title_col = _find_col(headers, ["title", "subject", "headline"])
    author_col = _find_col(headers, ["author", "user", "username", "name"])
    url_col = _find_col(headers, ["url", "link", "href"])
    platform_col = _find_col(headers, ["platform", "source", "network"])
    sub_col = _find_col(headers, ["subreddit", "source", "group", "channel", "community"])

    if not content_col:
        stats["error"] = "CSV must have a 'content' (or 'text'/'body'/'post') column"
        return stats

    for row in reader:
        stats["rows_parsed"] += 1
        content = row.get(content_col, "").strip()
        if not content:
            continue

        post_data = {
            "platform": row.get(platform_col, "manual").strip() if platform_col else "manual",
            "title": row.get(title_col, "").strip()[:500] if title_col else "",
            "content": content[:5000],
            "author": row.get(author_col, "").strip() if author_col else "",
            "url": row.get(url_col, "").strip() if url_col else "",
            "score": 0,
            "subreddit": row.get(sub_col, "").strip() if sub_col else "",
        }

        try:
            result = db.insert_raw_post(post_data)
            if result:
                stats["posts_inserted"] += 1
        except Exception as e:
            log.error("CSV row error: %s", e)
            stats["errors"] += 1

    log.info("CSV import: %d rows → %d inserted", stats["rows_parsed"], stats["posts_inserted"])
    return stats


def _find_col(headers: dict, candidates: list[str]) -> str | None:
    """Find the first matching column name from candidates."""
    for candidate in candidates:
        if candidate in headers:
            return headers[candidate]
    return None
