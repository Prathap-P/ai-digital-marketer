"""
Reddit platform publisher.

Reddit's PRAW library does not support native scheduled posts (that feature
is web-only).  Instead, this module uses APScheduler to fire the actual
submission 24 hours in the future, running it in a background thread.

Prerequisites
-------------
1. Create a "script" type app at https://www.reddit.com/prefs/apps.
2. Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, and
   REDDIT_PASSWORD in your .env file.

Post format expected from the Reddit system prompt
---------------------------------------------------
The LLM response must contain two sections:
    Title: <one-line title>
    Body:  <multi-line post body>

Lines before "Title:" and between the sections are ignored.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import praw
import praw.exceptions

from config import settings
from models.schemas import Platform as PlatformEnum
from models.schemas import PlatformDraft, ScheduleResult
from platforms.base import Platform
from services.scheduler import scheduler

logger = logging.getLogger(__name__)


def _parse_reddit_draft(content: str) -> tuple[str, str]:
    """Extract title and body from the LLM output.

    Expected format (case-insensitive section headers):
        Title: <title text>
        Body:
        <body text ...>

    Args:
        content: Raw string returned by generate_post.

    Returns:
        (title, body) tuple — both stripped of surrounding whitespace.

    Raises:
        ValueError: If either section cannot be located.
    """
    lines = content.splitlines()
    title: Optional[str] = None
    body_lines: list[str] = []
    in_body = False

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        if lower.startswith("title:") and title is None:
            title = stripped[len("title:"):].strip()
        elif lower.startswith("body:"):
            in_body = True
            # Inline body content after "Body:" label
            inline = stripped[len("body:"):].strip()
            if inline:
                body_lines.append(inline)
        elif in_body:
            body_lines.append(line)

    if not title:
        raise ValueError("Could not parse 'Title:' from Reddit draft content.")
    if not body_lines:
        raise ValueError("Could not parse 'Body:' from Reddit draft content.")

    return title, "\n".join(body_lines).strip()


def _submit_post(content: str, subreddit: str) -> None:
    """Perform the actual Reddit submission (called by APScheduler).

    Args:
        content:   Full draft content string (Title + Body format).
        subreddit: Target subreddit name (without r/ prefix).
    """
    logger.info("APScheduler: submitting Reddit post to r/%s", subreddit)
    try:
        title, body = _parse_reddit_draft(content)
    except ValueError as exc:
        logger.error("Failed to parse Reddit draft: %s", exc)
        return

    reddit = praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        username=settings.reddit_username,
        password=settings.reddit_password,
        user_agent=f"ai-digital-marketer:v1.0 (by u/{settings.reddit_username})",
    )
    try:
        submission = reddit.subreddit(subreddit).submit(title=title, selftext=body)
        logger.info(
            "Reddit post submitted successfully — submission ID: %s", submission.id
        )
    except praw.exceptions.PRAWException as exc:
        logger.error("Reddit submission failed: %s", exc)


class RedditPlatform(Platform):
    """Schedules a Reddit self-post via APScheduler + PRAW."""

    @property
    def name(self) -> str:
        return PlatformEnum.REDDIT.value

    def schedule(self, draft: PlatformDraft, post_at: datetime) -> ScheduleResult:
        """Schedule *draft* for publication on Reddit at *post_at*.

        The post is queued in APScheduler and submitted when the time arrives.

        Args:
            draft:   Must be a REDDIT PlatformDraft.
            post_at: UTC datetime for scheduled publication (must be future).

        Returns:
            ScheduleResult confirming the job was queued.

        Raises:
            ValueError: If the draft platform does not match or subreddit is missing.
            RuntimeError: If the scheduler job cannot be created.
        """
        if draft.platform != PlatformEnum.REDDIT:
            raise ValueError(
                f"RedditPlatform received a draft for '{draft.platform.value}'"
            )

        subreddit = draft.subreddit or (settings.reddit_default_subreddits_list[0] if settings.reddit_default_subreddits_list else None)
        if not subreddit:
            raise ValueError("No subreddit specified and no default configured.")

        if settings.dry_run:
            title, body = _parse_reddit_draft(draft.content)
            logger.info(
                "[DRY RUN] Would submit to r/%s at %s\nTitle: %s\nBody: %s",
                subreddit,
                post_at.isoformat(),
                title,
                body[:200],
            )
            return ScheduleResult(
                platform=PlatformEnum.REDDIT,
                scheduled_at_utc=post_at.isoformat(),
                status="dry_run",
                detail=f"Dry-run mode — would post to r/{subreddit}.",
            )

        run_at = post_at.astimezone(timezone.utc)
        job = scheduler.add_job(
            _submit_post,
            trigger="date",
            run_date=run_at,
            args=[draft.content, subreddit],
            id=f"reddit_{subreddit}_{int(run_at.timestamp())}",
            replace_existing=True,
        )

        logger.info(
            "Reddit post queued — job ID: %s, fires at %s, subreddit: r/%s",
            job.id,
            run_at.isoformat(),
            subreddit,
        )

        return ScheduleResult(
            platform=PlatformEnum.REDDIT,
            scheduled_at_utc=run_at.isoformat(),
            status="scheduled",
            detail=f"Job queued for r/{subreddit} (job ID: {job.id})",
        )
