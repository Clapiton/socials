"""
Analysis pipeline — processes unanalyzed posts through VADER + LLM.
"""

import logging
import db
from analysis.sentiment import passes_sentiment_filter, get_sentiment_score
from analysis.classifier import classify_post

logger = logging.getLogger(__name__)


def _notify_lead(lead_id: str) -> None:
    """Fire webhook for a new lead (non-blocking)."""
    try:
        import requests
        n8n_url = db.get_setting("n8n_webhook_url", "")
        if n8n_url:
            requests.post(n8n_url, json={"lead_id": lead_id}, timeout=10)
            logger.info(f"Webhook fired for lead {lead_id}")
    except Exception as e:
        logger.warning(f"Webhook failed for lead {lead_id}: {e}")


def run_pipeline(limit: int = 50) -> dict:
    """
    Process unanalyzed posts:
    1. Fetch unanalyzed raw_posts
    2. Apply VADER sentiment filter
    3. Classify with LLM
    4. Store results in analyzed_posts
    
    Returns summary stats.
    """
    settings = db.get_settings()
    services = settings.get("services", "")
    model = settings.get("llm_model", "gpt-4o-mini")
    sentiment_threshold = float(settings.get("sentiment_threshold", "-0.05"))

    stats = {
        "posts_fetched": 0,
        "sentiment_passed": 0,
        "sentiment_skipped": 0,
        "frustrated_detected": 0,
        "not_frustrated": 0,
        "errors": 0,
    }

    # 1. Fetch unanalyzed posts
    posts = db.get_unanalyzed_posts(limit=limit)
    stats["posts_fetched"] = len(posts)

    if not posts:
        logger.info("No unanalyzed posts found.")
        return stats

    logger.info(f"Processing {len(posts)} unanalyzed posts with model={model}")

    for post in posts:
        try:
            content = post.get("content", "") or post.get("title", "")
            if not content.strip():
                logger.debug(f"Skipping empty post {post['id']}")
                continue

            # 2. VADER pre-filter
            sentiment_score = get_sentiment_score(content)

            if not passes_sentiment_filter(content, threshold=sentiment_threshold):
                stats["sentiment_skipped"] += 1

                # Still store the analysis with is_frustrated = False
                db.insert_analysis({
                    "raw_post_id": post["id"],
                    "is_frustrated": False,
                    "confidence": 0.0,
                    "reason": f"Filtered by sentiment (score: {sentiment_score:.3f})",
                    "suggested_service": "none",
                    "sentiment_score": sentiment_score,
                })
                continue

            stats["sentiment_passed"] += 1

            # 3. LLM classification
            result = classify_post(content, services=services, model=model)

            # 4. Store result
            analysis_row = db.insert_analysis({
                "raw_post_id": post["id"],
                "is_frustrated": result["is_frustrated"],
                "confidence": result["confidence"],
                "reason": result["reason"],
                "suggested_service": result["suggested_service"],
                "sentiment_score": sentiment_score,
            })

            if result["is_frustrated"]:
                stats["frustrated_detected"] += 1
                logger.info(
                    f"🔥 Lead found! Confidence: {result['confidence']:.2f} — "
                    f"{result['reason'][:80]}"
                )
                # Insert into leads table and trigger webhook
                if analysis_row and result["confidence"] >= float(settings.get("confidence_threshold", 0.8)):
                    lead_row = db.insert_lead(analysis_row, post)
                    if lead_row:
                        _notify_lead(lead_row["id"])
            else:
                stats["not_frustrated"] += 1

        except Exception as e:
            logger.error(f"Error analyzing post {post.get('id', '?')}: {e}")
            stats["errors"] += 1

    logger.info(
        f"Analysis complete — Fetched: {stats['posts_fetched']}, "
        f"Sentiment pass: {stats['sentiment_passed']}, "
        f"Sentiment skip: {stats['sentiment_skipped']}, "
        f"Leads: {stats['frustrated_detected']}, "
        f"Not frustrated: {stats['not_frustrated']}, "
        f"Errors: {stats['errors']}"
    )
    return stats
