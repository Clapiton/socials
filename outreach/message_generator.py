"""
Outreach message generator — uses OpenAI to craft personalized outreach messages.
Creates empathetic, value-first messages based on the user's frustration context.
"""

import json
import logging
from openai import OpenAI
from config import OPENAI_API_KEY
import db

logger = logging.getLogger(__name__)


# ─── Prompt Templates ───────────────────────────────────────

EMAIL_PROMPT = """You are writing a friendly, helpful email to someone who expressed frustration online.
They are NOT expecting this message — so it must feel natural, empathetic, and not salesy.

Context about the person:
- Platform: {platform}
- Their post/comment: "{post_content}"
- What they're struggling with: {reason}
- Service that could help: {suggested_service}
- Your services: {your_services}

Write an email with:
1. A concise subject line (5-8 words)
2. A warm greeting
3. Brief acknowledgment that you noticed they were struggling (without being creepy)
4. 1-2 sentences showing you understand their problem
5. A soft offer to help (NOT a hard sell)
6. A friendly sign-off

Rules:
- Keep it under 150 words (body only)
- No corporate jargon
- Sound like a real person, not a template
- Don't mention "I saw your post on Reddit" — keep it vague ("I noticed you were looking for help with...")
- Include a clear but gentle call to action

Respond with ONLY valid JSON:
{{
    "subject": "the email subject line",
    "body": "the full email body"
}}"""


def generate_outreach_message(
    lead: dict,
    channel: str = "email",
    your_services: str = "",
) -> dict:
    """
    Generate a personalized outreach message for a lead.

    Args:
        lead: analyzed_post row with nested raw_posts data
        channel: 'email' (currently only email supported)
        your_services: comma-separated list of services you offer

    Returns:
        dict with 'subject' and 'body' keys
    """
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set — returning placeholder message")
        return {
            "subject": "Quick question about your project",
            "body": "Hi there! I noticed you might need help with a project. "
                    "I'd love to chat if you're interested. No pressure at all!",
        }

    raw_post = lead.get("raw_posts", {}) or {}
    post_content = raw_post.get("title", "") or raw_post.get("content", "")
    if raw_post.get("title") and raw_post.get("content"):
        post_content = f"{raw_post['title']}\n{raw_post['content']}"

    platform = raw_post.get("platform", "online")
    reason = lead.get("reason", "a project they need help with")
    suggested_service = lead.get("suggested_service", "professional help")

    # Get services from settings if not provided
    if not your_services:
        try:
            settings = db.get_settings()
            your_services = settings.get("services", "consulting,development")
        except Exception:
            your_services = "consulting,development"

    # Get model from settings
    try:
        settings = db.get_settings()
        model = settings.get("llm_model", "gpt-4o-mini")
    except Exception:
        model = "gpt-4o-mini"

    prompt = EMAIL_PROMPT.format(
        platform=platform,
        post_content=post_content[:500],
        reason=reason,
        suggested_service=suggested_service,
        your_services=your_services,
    )

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON response
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content)

        logger.info("Outreach message generated successfully")
        return {
            "subject": result.get("subject", "Quick question about your project"),
            "body": result.get("body", ""),
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response: {e}")
        return {
            "subject": "Quick question about your project",
            "body": content if content else "Hi! I'd love to help with your project.",
        }
    except Exception as e:
        logger.error(f"Error generating outreach message: {e}")
        return {
            "subject": "Quick question about your project",
            "body": "Hi there! I noticed you might need help with a project. "
                    "I'd love to chat if you're interested.",
        }
