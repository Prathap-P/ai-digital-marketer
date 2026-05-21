"""
Post generation orchestrator.

Responsibilities
----------------
1. Load the system prompt for each requested platform.
2. Call the LLM function with the user input + system prompt.
3. Return a list of PlatformDraft objects — one per platform.
"""

from __future__ import annotations

import logging
from pathlib import Path

from config import PROMPTS_DIR
from models.schemas import Platform, PlatformDraft
from services.llm_function import generate_post

logger = logging.getLogger(__name__)

# Map each platform to its prompt file inside prompts/.
_PROMPT_FILES: dict[Platform, str] = {
    Platform.LINKEDIN: "linkedin.md",
    Platform.REDDIT: "reddit.md",
}

def _load_system_prompt(platform: Platform) -> str:
    """Read and return the system prompt for *platform*.

    Args:
        platform: Target platform enum value.

    Returns:
        Prompt file content as a string.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    filename = _PROMPT_FILES[platform]
    prompt_path: Path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"System prompt not found for {platform.value}: {prompt_path}"
        )
    return prompt_path.read_text(encoding="utf-8")

def generate_drafts(
    input_text: str,
    platforms: list[Platform],
) -> list[PlatformDraft]:
    """Generate a post draft for every requested platform.

    Args:
        input_text: Combined user writeup + resource URLs.
        platforms: Platforms to generate posts for.

    Returns:
        A list of PlatformDraft objects in the same order as *platforms*.
    """
    drafts: list[PlatformDraft] = []

    for platform in platforms:
        logger.info("Generating draft for %s", platform.value)
        system_prompt = _load_system_prompt(platform)
        content = generate_post(input_text=input_text, system_prompt=system_prompt)
        drafts.append(PlatformDraft(platform=platform, content=content))
        logger.debug("Draft generated for %s (%d chars)", platform.value, len(content))

    return drafts

def regenerate_draft(
    follow_up: str,
    platform: Platform,
    existing_draft: str = "",
) -> PlatformDraft:
    """Regenerate a single platform draft using a follow-up instruction.

    Args:
        follow_up: Refinement instruction from the user.
        platform: Platform whose draft should be regenerated.
        existing_draft: The current draft text to give the model context.

    Returns:
        An updated PlatformDraft.
    """
    logger.info("Regenerating draft for %s with follow-up", platform.value)
    system_prompt = _load_system_prompt(platform)
    if existing_draft:
        input_text = f"[Existing draft:]\n{existing_draft}\n\n[Follow-up instruction:]\n{follow_up}"
    else:
        input_text = follow_up
    content = generate_post(input_text=input_text, system_prompt=system_prompt)
    return PlatformDraft(platform=platform, content=content)
