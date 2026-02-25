from __future__ import annotations

"""
Apify-based collectors — scrape Reddit, Twitter/X, Facebook
via Apify actors.  Only needs a single APIFY_API_TOKEN in .env.
"""

import os
import time
import logging
import requests
from datetime import datetime, timezone

import db

log = logging.getLogger(__name__)

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN", "")
BASE_URL = "https://api.apify.com/v2"

# ── Actor registry ───────────────────────────────────────────────────────────
ACTORS = {
    "reddit": {
        "actor_id": "trudax~reddit-scraper",
        "map": {  # Apify output field → raw_posts field
            "id": "post_id",
            "title": "title",
            "body": "content",
            "username": "author",
            "url": "url",
            "upVotes": "score",
            "parsedCommunityName": "subreddit",
        },
    },
    "twitter": {
        "actor_id": "apidojo~tweet-scraper",
        "map": {
            "id": "post_id",
            "text": "content",
            "author.userName": "author",
            "url": "url",
            "likeCount": "score",
        },
    },
    "facebook": {
        "actor_id": "apify~facebook-posts-scraper",
        "map": {
            "postId": "post_id",
            "text": "content",
            "pageName": "author",
            "url": "url",
            "likes": "score",
        },
    },
}


def _headers() -> dict:
    return {"Authorization": f"Bearer {APIFY_TOKEN}", "Content-Type": "application/json"}


def _run_actor(actor_id: str, run_input: dict, timeout: int = 120) -> list[dict]:
    """Start an Apify actor, wait for it, and return dataset items."""
    url = f"{BASE_URL}/acts/{actor_id}/runs"
    log.info("Starting Apify actor %s", actor_id)

    resp = requests.post(url, json=run_input, headers=_headers(), params={"timeout": timeout})
    resp.raise_for_status()
    run_data = resp.json()["data"]
    run_id = run_data["id"]
    dataset_id = run_data.get("defaultDatasetId")

    # Poll for completion
    status = run_data.get("status", "RUNNING")
    poll_url = f"{BASE_URL}/acts/{actor_id}/runs/{run_id}"
    elapsed = 0
    while status in ("RUNNING", "READY") and elapsed < timeout:
        time.sleep(5)
        elapsed += 5
        r = requests.get(poll_url, headers=_headers())
        r.raise_for_status()
        status = r.json()["data"]["status"]
        dataset_id = r.json()["data"].get("defaultDatasetId", dataset_id)

    if status != "SUCCEEDED":
        log.warning("Actor %s finished with status: %s", actor_id, status)
        return []

    # Fetch dataset
    ds_url = f"{BASE_URL}/datasets/{dataset_id}/items"
    r = requests.get(ds_url, headers=_headers(), params={"limit": 100})
    r.raise_for_status()
    return r.json()


def _nested_get(obj: dict, dotted_key: str):
    """Get a nested value like 'user.screen_name' from a dict."""
    keys = dotted_key.split(".")
    val = obj
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return None
    return val


def _map_to_post(item: dict, platform: str, field_map: dict) -> dict:
    """Map an Apify result item to our raw_posts schema."""
    post = {
        "platform": platform,
        "post_id": "",
        "title": "",
        "content": "",
        "author": "",
        "url": "",
        "score": 0,
        "subreddit": "",
    }
    for apify_field, our_field in field_map.items():
        val = _nested_get(item, apify_field)
        if val is not None:
            post[our_field] = val
    
    # Ensure post_id exists (fallback to URL hash or UUID)
    if not post.get("post_id"):
        import hashlib
        identifier = post.get("url") or post.get("content") or post.get("title") or str(time.time())
        post["post_id"] = f"{platform}-{hashlib.md5(identifier.encode()).hexdigest()[:12]}"
    
    return post


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    """Check if text matches any frustration keyword."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


# ── Platform-specific collect functions ──────────────────────────────────────

def collect_reddit(keywords: list[str], subreddits: list[str], limit: int = 25) -> dict:
    """Collect Reddit posts via Apify (trudax/reddit-scraper)."""
    if not APIFY_TOKEN:
        log.warning("APIFY_API_TOKEN not set — skipping Reddit (Apify)")
        return {"platform": "reddit", "source": "apify", "posts_inserted": 0, "skipped": True}

    actor = ACTORS["reddit"]
    run_input = {
        "startUrls": [{"url": f"https://www.reddit.com/r/{sub}/new/"} for sub in subreddits],
        "maxItems": limit * len(subreddits),
        "sort": "New",
        "type": "posts",
    }

    try:
        items = _run_actor(actor["actor_id"], run_input)
    except Exception as e:
        log.error("Reddit Apify error: %s", e)
        return {"platform": "reddit", "source": "apify", "posts_inserted": 0, "error": str(e)}

    return _process_items(items, "reddit", actor["map"], keywords)


def collect_twitter(keywords: list[str], limit: int = 25) -> dict:
    """Collect tweets via Apify (apidojo/tweet-scraper)."""
    if not APIFY_TOKEN:
        log.warning("APIFY_API_TOKEN not set — skipping Twitter")
        return {"platform": "twitter", "source": "apify", "posts_inserted": 0, "skipped": True}

    actor = ACTORS["twitter"]
    search_queries = [kw for kw in keywords[:5]]
    run_input = {
        "searchTerms": search_queries,
        "maxItems": limit,
        "sort": "Latest",
    }

    try:
        items = _run_actor(actor["actor_id"], run_input)
    except Exception as e:
        log.error("Twitter Apify error: %s", e)
        return {"platform": "twitter", "source": "apify", "posts_inserted": 0, "error": str(e)}

    return _process_items(items, "twitter", actor["map"], keywords)


def collect_facebook(keywords: list[str], limit: int = 25) -> dict:
    """Collect Facebook page posts via Apify (apify/facebook-posts-scraper).
    Requires Facebook page URLs — searches are not supported by this actor.
    """
    if not APIFY_TOKEN:
        log.warning("APIFY_API_TOKEN not set — skipping Facebook")
        return {"platform": "facebook", "source": "apify", "posts_inserted": 0, "skipped": True}

    actor = ACTORS["facebook"]
    # This actor needs page/profile URLs, not search terms.
    # For keyword-based discovery, we construct search URLs as a fallback.
    run_input = {
        "startUrls": [{"url": f"https://www.facebook.com/search/posts/?q={kw}"} for kw in keywords[:3]],
        "maxPosts": limit,
        "maxPostComments": 0,
    }

    try:
        items = _run_actor(actor["actor_id"], run_input)
    except Exception as e:
        log.error("Facebook Apify error: %s", e)
        return {"platform": "facebook", "source": "apify", "posts_inserted": 0, "error": str(e)}

    return _process_items(items, "facebook", actor["map"], keywords)


# ── Shared processing ───────────────────────────────────────────────────────

def _process_items(items: list[dict], platform: str, field_map: dict, keywords: list[str]) -> dict:
    """Map, filter, deduplicate, and insert Apify results."""
    inserted = 0
    duplicates = 0
    filtered = 0

    for item in items:
        post = _map_to_post(item, platform, field_map)
        full_text = f"{post.get('title', '')} {post.get('content', '')}"

        if not full_text.strip():
            filtered += 1
            continue

        if keywords and not _matches_keywords(full_text, keywords):
            filtered += 1
            continue

        try:
            result = db.insert_raw_post(post)
            if result:
                inserted += 1
            else:
                duplicates += 1
        except Exception as e:
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                duplicates += 1
            else:
                log.error("Error inserting %s post: %s", platform, e)

    log.info("%s (Apify): %d items → %d inserted, %d duplicates, %d filtered",
             platform, len(items), inserted, duplicates, filtered)

    return {
        "platform": platform,
        "source": "apify",
        "items_fetched": len(items),
        "posts_inserted": inserted,
        "duplicates_skipped": duplicates,
        "filtered_out": filtered,
    }


def collect_all(keywords: list[str], subreddits: list[str] | None = None, limit: int = 25) -> list[dict]:
    """Run all Apify collectors and return combined results."""
    results = []
    # Use a default subreddit if none provided
    subs = subreddits or ["freelance", "webdev"]
    results.append(collect_reddit(keywords, subs, limit))
    results.append(collect_twitter(keywords, limit))
    results.append(collect_facebook(keywords, limit))
    return results


def collect_posts(keywords: list[str]) -> dict:
    """Entry point for app.py to run all Apify collectors."""
    results = collect_all(keywords)
    # Combine stats for the dashboard
    combined = {
        "platform": "social_bundle",
        "posts_inserted": sum(r.get("posts_inserted", 0) for r in results if isinstance(r, dict)),
        "duplicates_skipped": sum(r.get("duplicates_skipped", 0) for r in results if isinstance(r, dict)),
    }
    return combined
