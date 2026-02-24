from __future__ import annotations

"""
LLM-based frustration classifier using OpenAI.
"""

import json
import logging
import time
from openai import OpenAI
from config import OPENAI_API_KEY, CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)

_openai_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    """Get or create the OpenAI client singleton."""
    global _openai_client
    if _openai_client is None:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY must be set in .env")
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def classify_post(content: str, services: str, model: str = "gpt-4o-mini", max_retries: int = 3) -> dict:
    """
    Classify a post using the LLM.
    
    Returns:
        dict with keys: is_frustrated, confidence, reason, suggested_service
    """
    client = get_openai_client()
    prompt = CLASSIFICATION_PROMPT.format(post_content=content, services=services)

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a frustration detection assistant. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=300,
            )

            raw_text = response.choices[0].message.content.strip()

            # Strip markdown code fences if present
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[-1]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3].strip()

            result = json.loads(raw_text)

            # Validate required fields
            return {
                "is_frustrated": bool(result.get("is_frustrated", False)),
                "confidence": float(result.get("confidence", 0.0)),
                "reason": str(result.get("reason", "")),
                "suggested_service": str(result.get("suggested_service", "none")),
            }

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response (attempt {attempt + 1}): {e}")
            logger.debug(f"Raw response: {raw_text}")
        except Exception as e:
            logger.error(f"OpenAI API error (attempt {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            wait = 2 ** attempt
            logger.info(f"Retrying in {wait}s...")
            time.sleep(wait)

    # Return safe defaults on total failure
    logger.error("All classification attempts failed. Returning defaults.")
    return {
        "is_frustrated": False,
        "confidence": 0.0,
        "reason": "Classification failed after retries",
        "suggested_service": "none",
    }
