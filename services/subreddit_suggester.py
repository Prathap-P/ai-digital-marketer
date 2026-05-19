"""
Subreddit suggestion service.

Uses the same LLM function contract as post generation, with a dedicated
system prompt that instructs the model to return a JSON list of subreddit names.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from config import PROMPTS_DIR, settings
from services.llm_function import generate_post

logger = logging.getLogger(__name__)

_PROMPT_FILE = "subreddit_suggester.md"
_FALLBACK_SUBREDDITS = ["MachineLearning", "singularity", "technology", "Futurology", "artificial"]


def _load_prompt() -> str:
    path: Path = PROMPTS_DIR / _PROMPT_FILE
    if not path.exists():
        raise FileNotFoundError(f"Subreddit suggester prompt not found: {path}")
    return path.read_text(encoding="utf-8")


_SUBREDDIT_RE = re.compile(r"^[A-Za-z0-9_]{2,21}$")


def _is_valid_subreddit_name(name: str) -> bool:
    """Return True if *name* looks like a real subreddit name."""
    return bool(_SUBREDDIT_RE.match(name))


def _parse_subreddits(raw: str) -> list[str]:
    """Extract a list of subreddit names from the LLM's raw output.

    Tries strict JSON parse first, then falls back to extracting
    quoted tokens that match the subreddit name pattern.

    Args:
        raw: Raw string returned by generate_post.

    Returns:
        List of valid subreddit name strings (without r/ prefix), deduplicated.
        Returns an empty list if no valid names are found.
    """
    raw = raw.strip()

    # Strip markdown code fences if the model added them
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(
            line for line in lines if not line.startswith("```")
        ).strip()

    def _clean_and_validate(names: list[str]) -> list[str]:
        cleaned = [n.strip().lstrip("r/").strip() for n in names if n.strip()]
        valid = [n for n in cleaned if _is_valid_subreddit_name(n)]
        return list(dict.fromkeys(valid))  # deduplicate, preserve order

    # Attempt strict JSON parse
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            names = _clean_and_validate([str(s) for s in parsed if s])
            if names:
                return names
    except json.JSONDecodeError:
        pass

    # Fallback: extract short quoted tokens that look like subreddit names
    tokens = re.findall(r'"([^"]+)"|\'([^\']+)\'', raw)
    candidates = [a or b for a, b in tokens]
    names = _clean_and_validate(candidates)
    if names:
        return names

    logger.warning("Could not parse subreddit suggestions from LLM output: %r", raw[:200])
    return []


def suggest_subreddits(input_text: str) -> list[str]:
    """Return a ranked list of suggested subreddits for *input_text*.

    Falls back to the configured defaults if the LLM call fails or
    returns unparseable output.

    Args:
        input_text: The same combined user input used for post generation.

    Returns:
        List of subreddit names (without r/ prefix), 4–7 items.
    """
    try:
        system_prompt = _load_prompt()
        raw = generate_post(input_text=input_text, system_prompt=system_prompt)
        suggestions = _parse_subreddits(raw)
        if suggestions:
            logger.info("Subreddit suggestions: %s", suggestions)
            return suggestions
    except Exception as exc:
        logger.warning("Subreddit suggestion failed (%s); using defaults.", exc)

    fallback = settings.reddit_default_subreddits_list or _FALLBACK_SUBREDDITS
    logger.info("Using fallback subreddits: %s", fallback)
    return fallback
