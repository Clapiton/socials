"""
Centralized configuration loader.
Reads .env for API credentials only.
Runtime settings (subreddits, services, threshold, model) come from Supabase settings table.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- API Credentials (from .env) ---
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "SocialListener/1.0")

# --- Dashboard ---
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

# --- Default Settings (used to seed the settings table on first run) ---
DEFAULT_SETTINGS = {
    "subreddits": "freelance,webdev,forhire,smallbusiness,startups",
    "services": "web development,automation,design,consulting",
    "confidence_threshold": "0.8",
    "llm_model": "gpt-4o-mini",
    "poll_interval_minutes": "10",
    "sentiment_threshold": "-0.05",
    "frustration_keywords": "frustrated,stuck,can't figure out,need help with,struggling,impossible,giving up,so hard,anyone know how,desperate",
    "mastodon_instances": "mastodon.social,fosstodon.org,techhub.social",
    "n8n_webhook_url": "",
}

# --- Frustration Detection Prompt ---
CLASSIFICATION_PROMPT = """You are an expert at detecting when someone is genuinely frustrated about getting a job or task done and could benefit from professional help.

Analyze the following social media post and determine:
1. Is the author genuinely frustrated about completing a specific job or task?
2. How confident are you (0.0 to 1.0)?
3. Why do you think so?
4. What professional service could help them?

IMPORTANT:
- Only flag posts where someone is struggling with a SPECIFIC task they need done (not general life complaints).
- Look for actionable frustration — someone who might hire a professional to solve their problem.
- Do NOT flag jokes, sarcasm, or venting about unrelated topics.

Post:
\"\"\"
{post_content}
\"\"\"

Available services the user offers: {services}

Respond with ONLY valid JSON:
{{
    "is_frustrated": true/false,
    "confidence": 0.0-1.0,
    "reason": "brief explanation",
    "suggested_service": "which service from the list could help, or 'none'"
}}"""
