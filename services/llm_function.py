"""
LLM function — LM Studio / ChatOpenAI integration.

Single integration point for the external language model.
Uses LM Studio's OpenAI-compatible API via langchain-openai.

Signature must not change — callers depend on it.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import settings

def generate_post(input_text: str, system_prompt: str) -> str:
    """Generate a platform-specific post via LM Studio.

    Args:
        input_text: User context (writeup + resource URLs) or a follow-up
                    refinement instruction.
        system_prompt: Platform-specific instructions loaded from prompts/.

    Returns:
        The generated post content as a plain string.

    Raises:
        RuntimeError: If the underlying model call fails.
    """
    llm = ChatOpenAI(
        base_url=settings.lm_studio_base_url,
        api_key="test",
        temperature=0.6,
        model=settings.mlx_qwen_model_id,
        top_p=0.9,
        max_completion_tokens=15000,
        model_kwargs={"frequency_penalty": 0.3, "presence_penalty": 0.2},
        extra_body={"min_p": 0, "repeat_penalty": 1.15},
        timeout=3600,
    )

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=input_text)]

    try:
        response = llm.invoke(messages)
    except Exception as e:
        raise RuntimeError(f"LM Studio model call failed: {e}") from e

    return str(response.content)
