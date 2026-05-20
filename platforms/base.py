"""
Abstract base class for all posting platforms.

To add a new platform:
1. Create a new module in platforms/ that subclasses Platform.
2. Implement the `schedule` method.
3. Register the class in the PLATFORM_REGISTRY in config.py (or main.py).

That is the only change required — no other code needs to be touched.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from models.schemas import PlatformDraft, ScheduleResult


class Platform(ABC):
    """Contract that every platform publisher must fulfil."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable platform identifier (e.g. 'linkedin', 'reddit')."""

    @abstractmethod
    def schedule(
        self,
        draft: PlatformDraft,
        post_at: datetime,
        record_id: Optional[int] = None,
    ) -> ScheduleResult:
        """Schedule *draft* to be published at *post_at* (UTC).

        Args:
            draft:     The PlatformDraft to publish.
            post_at:   Exact UTC datetime when the post should go live.
            record_id: Optional PostRecord primary key.  Platforms that use
                       background jobs (e.g. Reddit/APScheduler) should pass
                       this to their job so they can update the DB row once the
                       post is actually submitted.

        Returns:
            A ScheduleResult describing the outcome.

        Raises:
            RuntimeError: If the scheduling call fails.
        """
