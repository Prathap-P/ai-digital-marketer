"""Pydantic models shared across the application."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Platform(str, Enum):
    """Supported posting platforms."""

    LINKEDIN = "linkedin"
    REDDIT = "reddit"


class PlatformDraft(BaseModel):
    """A generated post draft for a single platform."""

    platform: Platform
    content: str
    subreddit: Optional[str] = None        # Reddit only
    media_urn: Optional[str] = None        # LinkedIn only — asset URN after upload
    media_type: Optional[str] = None       # LinkedIn only — "image" or "document"


class GenerateRequest(BaseModel):
    """Payload submitted from the input form."""

    writeup: str = Field(..., min_length=1, description="User-supplied context / writeup")
    urls: list[str] = Field(default_factory=list, description="Resource URLs to include")
    platforms: list[Platform] = Field(
        default_factory=list,
        description="Platforms to generate posts for",
    )

    @property
    def combined_input(self) -> str:
        """Concatenate writeup and URLs into a single input string for the LLM."""
        parts = [self.writeup.strip()]
        if self.urls:
            parts.append("\nReference URLs:")
            parts.extend(f"- {url.strip()}" for url in self.urls if url.strip())
        return "\n".join(parts)


class RegenerateRequest(BaseModel):
    """Payload for a per-platform regeneration request."""

    session_id: str
    platform: Platform
    follow_up: str = Field(..., min_length=1, description="Follow-up instruction for refinement")


class ScheduleRequest(BaseModel):
    """Payload for scheduling a single platform's draft."""

    session_id: str
    platform: Platform
    subreddit: Optional[str] = None   # Reddit only — overrides the draft's stored subreddit


class ScheduleResult(BaseModel):
    """Response after a successful schedule operation."""

    platform: Platform
    scheduled_at_utc: str  # ISO-8601 string
    status: str = "scheduled"
    detail: Optional[str] = None
