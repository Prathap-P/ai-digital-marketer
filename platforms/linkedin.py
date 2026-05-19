"""
LinkedIn platform publisher.

Uses the LinkedIn UGC Posts v2 REST API with native scheduled publishing
(the `scheduledPublishTime` field).

Prerequisites
-------------
1. Create a LinkedIn Developer app at https://developer.linkedin.com.
2. Request the `w_member_social` permission scope.
3. Complete the OAuth 2.0 flow to obtain an access token.
4. Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_ID in your .env file.

Note: LinkedIn's scheduled post feature via API requires the appropriate
permission tier.  If you receive a 403, verify your app's granted scopes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from config import settings
from models.schemas import Platform as PlatformEnum
from models.schemas import PlatformDraft, ScheduleResult
from platforms.base import Platform
from services import linkedin_auth
from typing import Optional

logger = logging.getLogger(__name__)

_LINKEDIN_API_BASE = "https://api.linkedin.com/v2"

def _to_epoch_ms(dt: datetime) -> int:
    """Convert a UTC datetime to milliseconds since epoch."""
    utc_dt = dt.astimezone(timezone.utc)
    return int(utc_dt.timestamp() * 1_000)

class LinkedInPlatform(Platform):
    """Schedules a post on LinkedIn using the UGC Posts API."""

    @property
    def name(self) -> str:
        return PlatformEnum.LINKEDIN.value

    def schedule(
        self,
        draft: PlatformDraft,
        post_at: datetime,
        record_id: Optional[int] = None,  # noqa: ARG002 — not needed for native scheduling
    ) -> ScheduleResult:
        """Schedule *draft* for publication on LinkedIn at *post_at*.

        Args:
            draft:     Must be a LINKEDIN PlatformDraft.
            post_at:   UTC datetime for scheduled publication (must be future).
            record_id: Unused by LinkedIn (native scheduling; no callback).

        Returns:
            ScheduleResult with the scheduled timestamp and LinkedIn post ID.

        Raises:
            ValueError: If the draft platform does not match.
            RuntimeError: If the API call fails.
        """
        if draft.platform != PlatformEnum.LINKEDIN:
            raise ValueError(
                f"LinkedInPlatform received a draft for '{draft.platform.value}'"
            )

        if draft.media_urn:
            # Media post via Posts API — publishes immediately (no scheduling support)
            if settings.dry_run:
                logger.info(
                    "[DRY RUN] Would publish LinkedIn media post immediately with URN %s",
                    draft.media_urn,
                )
                return ScheduleResult(
                    platform=PlatformEnum.LINKEDIN,
                    scheduled_at_utc=datetime.now(timezone.utc).isoformat(),
                    status="dry_run",
                    detail=f"Dry-run mode — would publish media post immediately with URN {draft.media_urn}",
                )

            logger.warning(
                "LinkedIn media post will be published immediately (Posts API does not support scheduling)."
            )

            access_token = linkedin_auth.get_token()
            person_id = linkedin_auth.get_person_id()
            if not access_token or not person_id:
                raise RuntimeError(
                    "LinkedIn is not connected. Visit /auth/linkedin to authorise the app."
                )

            payload = {
                "author": f"urn:li:person:{person_id}",
                "commentary": draft.content,
                "visibility": "PUBLIC",
                "distribution": {
                    "feedDistribution": "MAIN_FEED",
                    "targetEntities": [],
                    "thirdPartyDistributionChannels": [],
                },
                "content": {
                    "media": {
                        "id": draft.media_urn,
                    }
                },
                "lifecycleState": "PUBLISHED",
                "isReshareDisabledByAuthor": False,
            }

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "LinkedIn-Version": "202501",
                "X-Restli-Protocol-Version": "2.0.0",
            }

            response = requests.post(
                "https://api.linkedin.com/rest/posts",
                json=payload,
                headers=headers,
                timeout=15,
            )

            if not response.ok:
                raise RuntimeError(
                    f"LinkedIn Posts API error {response.status_code}: {response.text}"
                )

            post_id = response.headers.get("x-restli-id", "unknown")
            logger.info("LinkedIn media post published immediately — ID: %s", post_id)

            return ScheduleResult(
                platform=PlatformEnum.LINKEDIN,
                scheduled_at_utc=datetime.now(timezone.utc).isoformat(),
                status="published",
                detail=f"LinkedIn post ID: {post_id} (published immediately — Posts API does not support scheduling)",
            )

        else:
            # Text-only post via UGC Posts API — uses scheduledPublishTime
            if settings.dry_run:
                logger.info(
                    "[DRY RUN] Would schedule LinkedIn post at %s:\n%s",
                    post_at.isoformat(),
                    draft.content,
                )
                return ScheduleResult(
                    platform=PlatformEnum.LINKEDIN,
                    scheduled_at_utc=post_at.isoformat(),
                    status="dry_run",
                    detail="Dry-run mode — no API call was made.",
                )

            access_token = linkedin_auth.get_token()
            person_id = linkedin_auth.get_person_id()
            if not access_token or not person_id:
                raise RuntimeError(
                    "LinkedIn is not connected. Visit /auth/linkedin to authorise the app."
                )

            payload = {
                "author": f"urn:li:person:{person_id}",
                "lifecycleState": "DRAFT",
                "scheduledPublishTime": _to_epoch_ms(post_at),
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": draft.content},
                        "shareMediaCategory": "NONE",
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                },
            }

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            }

            response = requests.post(
                f"{_LINKEDIN_API_BASE}/ugcPosts",
                json=payload,
                headers=headers,
                timeout=15,
            )

            if not response.ok:
                raise RuntimeError(
                    f"LinkedIn API error {response.status_code}: {response.text}"
                )

            post_id = response.headers.get("x-restli-id", "unknown")
            logger.info("LinkedIn post scheduled — ID: %s at %s", post_id, post_at.isoformat())

            return ScheduleResult(
                platform=PlatformEnum.LINKEDIN,
                scheduled_at_utc=post_at.isoformat(),
                status="scheduled",
                detail=f"LinkedIn post ID: {post_id}",
            )
