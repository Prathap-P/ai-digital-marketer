"""
LLM function contract.

This is the single integration point for the external language model.
Replace the stub body with the real implementation when ready.

Contract
--------
- `input_text`    : The full user-supplied context (writeup + URLs).
  For follow-up calls this will be the follow-up instruction only;
  the cloud model owns the conversation history.
- `system_prompt` : The platform-specific system prompt loaded from prompts/.
- Returns         : A plain string containing the generated post.

The signature must not change — callers depend on it.
"""

from __future__ import annotations


def generate_post(input_text: str, system_prompt: str) -> str:  # noqa: ARG001
    """Generate a platform-specific post.

    Args:
        input_text: User context (writeup + resource URLs) or a follow-up
                    refinement instruction.
        system_prompt: Platform-specific instructions loaded from prompts/.

    Returns:
        The generated post content as a plain string.

    Raises:
        RuntimeError: If the underlying model call fails.
    """
    # ── STUB ──────────────────────────────────────────────────────────────────
    # Replace the block below with the real API / SDK call.
    # The function must return a non-empty string.
    # ─────────────────────────────────────────────────────────────────────────
    preview = input_text[:120].replace("\n", " ")
    return (
        f"[STUB RESPONSE]\n\n"
        f"This is a placeholder post generated from the input:\n"
        f'"{preview}…"\n\n'
        f"Replace services/llm_function.py with the real model call."
    )
