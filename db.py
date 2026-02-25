from __future__ import annotations

"""
Database layer — Supabase client and helper functions.
"""

import logging
from datetime import datetime, timezone
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY, DEFAULT_SETTINGS

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_client() -> Client:
    """Get or create the Supabase client singleton."""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


# ─── Settings ───────────────────────────────────────────────

def get_settings() -> dict:
    """Fetch all settings as a dict. Seeds defaults if table is empty."""
    client = get_client()
    result = client.table("settings").select("key, value").execute()
    settings = {row["key"]: row["value"] for row in result.data}

    # Seed missing defaults
    for key, default_value in DEFAULT_SETTINGS.items():
        if key not in settings:
            client.table("settings").upsert({"key": key, "value": default_value}).execute()
            settings[key] = default_value

    return settings


def update_setting(key: str, value: str) -> None:
    """Update a single setting."""
    client = get_client()
    client.table("settings").upsert({"key": key, "value": value}).execute()
    logger.info(f"Setting '{key}' updated to '{value}'")


def get_setting(key: str, default: str = "") -> str:
    """Get a single setting value."""
    settings = get_settings()
    return settings.get(key, default)


# ─── Raw Posts ──────────────────────────────────────────────

def check_duplicate(platform: str, post_id: str) -> bool:
    """Check if a post already exists."""
    client = get_client()
    result = (
        client.table("raw_posts")
        .select("id")
        .eq("platform", platform)
        .eq("post_id", post_id)
        .execute()
    )
    return len(result.data) > 0


def insert_raw_post(post_data: dict) -> dict | None:
    """Insert a raw post. Returns the inserted row or None if duplicate."""
    if check_duplicate(post_data["platform"], post_data["post_id"]):
        logger.debug(f"Duplicate post skipped: {post_data['platform']}/{post_data['post_id']}")
        return None

    client = get_client()
    result = client.table("raw_posts").insert(post_data).execute()
    if result.data:
        logger.info(f"Inserted post: {post_data['platform']}/{post_data['post_id']}")
        return result.data[0]
    return None


def get_raw_posts(limit: int = 50, offset: int = 0, platform: str | None = None) -> list[dict]:
    """Fetch raw posts with optional platform filter, ordered by collected_at desc."""
    client = get_client()
    query = client.table("raw_posts").select("*").order("collected_at", desc=True)
    if platform:
        query = query.eq("platform", platform)
    result = query.range(offset, offset + limit - 1).execute()
    return result.data


# ─── Analyzed Posts ─────────────────────────────────────────

def get_unanalyzed_posts(limit: int = 50) -> list[dict]:
    """Fetch raw posts that haven't been analyzed yet."""
    client = get_client()

    # Get IDs of already-analyzed posts
    analyzed = client.table("analyzed_posts").select("raw_post_id").execute()
    analyzed_ids = {row["raw_post_id"] for row in analyzed.data}

    # Get all raw posts
    all_posts = client.table("raw_posts").select("*").order("collected_at", desc=True).limit(limit * 2).execute()

    # Filter out analyzed ones  
    unanalyzed = [p for p in all_posts.data if p["id"] not in analyzed_ids]
    return unanalyzed[:limit]


def insert_analysis(analysis_data: dict) -> dict | None:
    """Insert an analysis result. Returns the inserted row."""
    client = get_client()
    result = client.table("analyzed_posts").insert(analysis_data).execute()
    if result.data:
        logger.info(f"Analysis stored for post: {analysis_data['raw_post_id']}")
        return result.data[0]
    return None


def get_leads(limit: int = 50, offset: int = 0) -> list[dict]:
    """Fetch qualified leads from the leads table, ordered by confidence desc."""
    client = get_client()
    result = (
        client.table("leads")
        .select("*")
        .order("confidence", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return result.data


# ─── Leads ──────────────────────────────────────────────────

def insert_lead(analyzed_post: dict, raw_post: dict) -> dict | None:
    """Insert a qualified lead into the leads table (denormalized for n8n)."""
    client = get_client()
    lead_data = {
        "analyzed_post_id": analyzed_post["id"],
        "raw_post_id": raw_post["id"],
        "confidence": analyzed_post.get("confidence", 0),
        "reason": analyzed_post.get("reason", ""),
        "suggested_service": analyzed_post.get("suggested_service", ""),
        "sentiment_score": analyzed_post.get("sentiment_score"),
        "platform": raw_post.get("platform", ""),
        "author": raw_post.get("author", ""),
        "post_title": raw_post.get("title", ""),
        "post_content": raw_post.get("content", ""),
        "post_url": raw_post.get("url", ""),
        "outreach_subject": analyzed_post.get("outreach_subject"),
        "outreach_body": analyzed_post.get("outreach_body"),
        "contact_email": analyzed_post.get("contact_email"),
        "status": "new",
    }
    try:
        result = client.table("leads").insert(lead_data).execute()
        if result.data:
            logger.info(f"Lead inserted: {lead_data['platform']}/{lead_data['author']}")
            return result.data[0]
    except Exception as e:
        # Handle duplicate (UNIQUE constraint on analyzed_post_id)
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            logger.debug(f"Lead already exists for analyzed_post {analyzed_post['id']}")
        else:
            logger.error(f"Error inserting lead: {e}")
    return None


# ─── Outreach ───────────────────────────────────────────────

def get_outreach(limit: int = 50, offset: int = 0) -> list[dict]:
    """Fetch outreach records."""
    client = get_client()
    result = (
        client.table("outreach")
        .select("*, analyzed_posts(*, raw_posts(*))")
        .order("sent_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return result.data


def insert_outreach(outreach_data: dict) -> dict | None:
    """Insert an outreach record. Returns the inserted row."""
    client = get_client()
    result = client.table("outreach").insert(outreach_data).execute()
    if result.data:
        logger.info(f"Outreach logged: {outreach_data.get('channel')} / {outreach_data.get('status')}")
        return result.data[0]
    return None


def update_outreach_status(outreach_id: str, status: str, response: str | None = None) -> dict | None:
    """Update an outreach record's status."""
    client = get_client()
    update = {"status": status}
    if response is not None:
        update["response_received"] = response
    result = (
        client.table("outreach")
        .update(update)
        .eq("id", outreach_id)
        .execute()
    )
    if result.data:
        logger.info(f"Outreach {outreach_id} updated to {status}")
        return result.data[0]
    return None


def get_lead_by_id(lead_id: str) -> dict | None:
    """Fetch a single lead from the leads table by its unique ID."""
    client = get_client()
    result = (
        client.table("leads")
        .select("*")
        .eq("id", lead_id)
        .execute()
    )
    if result.data:
        return result.data[0]
    return None


# ─── Stats ──────────────────────────────────────────────────

def get_stats() -> dict:
    """Return summary statistics."""
    client = get_client()

    total_posts = client.table("raw_posts").select("id", count="exact").execute()
    total_leads = (
        client.table("analyzed_posts")
        .select("id", count="exact")
        .eq("is_frustrated", True)
        .execute()
    )
    total_analyzed = client.table("analyzed_posts").select("id", count="exact").execute()
    total_outreach = client.table("outreach").select("id", count="exact").execute()
    outreach_replied = (
        client.table("outreach")
        .select("id", count="exact")
        .eq("status", "replied")
        .execute()
    )

    outreach_count = total_outreach.count or 0
    replied_count = outreach_replied.count or 0

    return {
        "total_posts": total_posts.count or 0,
        "total_analyzed": total_analyzed.count or 0,
        "total_leads": total_leads.count or 0,
        "total_outreach": outreach_count,
        "response_rate": round(replied_count / outreach_count * 100, 1) if outreach_count > 0 else 0,
    }
