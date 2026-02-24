from __future__ import annotations

"""
VADER sentiment pre-filter.
Posts with negative sentiment pass through to the LLM classifier.
"""

import logging
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

_analyzer: SentimentIntensityAnalyzer | None = None


def get_analyzer() -> SentimentIntensityAnalyzer:
    """Lazy-load the VADER analyzer."""
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


def get_sentiment_score(text: str) -> float:
    """Return the VADER compound sentiment score for text. Range: -1.0 to +1.0."""
    analyzer = get_analyzer()
    scores = analyzer.polarity_scores(text)
    return scores["compound"]


def passes_sentiment_filter(text: str, threshold: float = -0.05) -> bool:
    """
    Returns True if the text has negative enough sentiment to warrant LLM analysis.
    Lower compound scores = more negative sentiment.
    """
    score = get_sentiment_score(text)
    passes = score <= threshold
    logger.debug(f"Sentiment score: {score:.3f} (threshold: {threshold}) — {'PASS' if passes else 'SKIP'}")
    return passes
