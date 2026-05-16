"""
SQLite-backed post history store.

Uses SQLModel (thin wrapper around SQLAlchemy + Pydantic) so the schema stays
close to our existing Pydantic models and is easy to migrate later.

Database location: ./data/history.db  (auto-created on first run)

Table: postrecord
-----------------
id              INTEGER   Primary key, auto-incremented
platform        TEXT      "linkedin" | "reddit"
subreddit       TEXT      Reddit only — null for LinkedIn
content_preview TEXT      First 250 characters of the post content
scheduled_at    DATETIME  UTC datetime the post is/was scheduled for
status          TEXT      "scheduled" | "posted" | "failed"
post_id         TEXT      Platform-native ID (e.g. Reddit submission ID)
post_url        TEXT      Direct link to the live post (if available)
error_detail    TEXT      Error message if status == "failed"
created_at      DATETIME  UTC datetime the record was created
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select

logger = logging.getLogger(__name__)

# ── DB path & engine ───────────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).parent.parent / "data"
_DB_PATH = _DATA_DIR / "history.db"
_ENGINE = None  # initialised lazily by init_db()

_CONTENT_PREVIEW_LEN = 250


# ── Schema ─────────────────────────────────────────────────────────────────────
class PostRecord(SQLModel, table=True):
    """One row = one scheduled (or attempted) post."""

    id: Optional[int] = Field(default=None, primary_key=True)
    platform: str
    subreddit: Optional[str] = None
    content_preview: str
    scheduled_at: datetime
    status: str = "scheduled"           # scheduled | posted | failed
    post_id: Optional[str] = None       # platform-native ID
    post_url: Optional[str] = None      # direct link to live post
    error_detail: Optional[str] = None  # populated when status == "failed"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ── Engine helpers ─────────────────────────────────────────────────────────────
def init_db() -> None:
    """Create the data directory and initialise the database tables.

    Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS internally.
    Should be called once during application startup.
    """
    global _ENGINE  # noqa: PLW0603
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _ENGINE = create_engine(
        f"sqlite:///{_DB_PATH}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(_ENGINE)
    logger.info("Database initialised at %s", _DB_PATH)


def _get_engine():
    if _ENGINE is None:
        raise RuntimeError("Database not initialised — call init_db() first.")
    return _ENGINE


# ── CRUD ───────────────────────────────────────────────────────────────────────
def create_post_record(
    platform: str,
    content: str,
    scheduled_at: datetime,
    subreddit: Optional[str] = None,
) -> int:
    """Insert a new PostRecord and return its generated ID.

    Args:
        platform:     Platform name ("linkedin" or "reddit").
        content:      Full post content — stored as a preview.
        scheduled_at: UTC datetime the post is scheduled for.
        subreddit:    Target subreddit (Reddit only).

    Returns:
        The auto-generated integer primary key.
    """
    record = PostRecord(
        platform=platform,
        subreddit=subreddit,
        content_preview=content[:_CONTENT_PREVIEW_LEN],
        scheduled_at=scheduled_at,
    )
    with Session(_get_engine()) as session:
        session.add(record)
        session.commit()
        session.refresh(record)
        record_id = record.id
    logger.info("PostRecord created — id=%s platform=%s", record_id, platform)
    return record_id  # type: ignore[return-value]


def update_post_record(
    record_id: int,
    status: str,
    post_id: Optional[str] = None,
    post_url: Optional[str] = None,
    error_detail: Optional[str] = None,
) -> None:
    """Update the status (and optional metadata) of an existing PostRecord.

    Args:
        record_id:    Primary key of the record to update.
        status:       New status: "scheduled" | "posted" | "failed".
        post_id:      Platform-native post ID (set when status == "posted").
        post_url:     Direct URL of the live post (set when status == "posted").
        error_detail: Error message (set when status == "failed").
    """
    with Session(_get_engine()) as session:
        record = session.get(PostRecord, record_id)
        if record is None:
            logger.warning("update_post_record: record %s not found", record_id)
            return
        record.status = status
        if post_id is not None:
            record.post_id = post_id
        if post_url is not None:
            record.post_url = post_url
        if error_detail is not None:
            record.error_detail = error_detail
        session.add(record)
        session.commit()
    logger.info("PostRecord %s updated → status=%s", record_id, status)


def list_post_records(limit: int = 100) -> list[PostRecord]:
    """Return the most recent *limit* records, newest first.

    Args:
        limit: Maximum number of records to return.

    Returns:
        List of PostRecord objects ordered by scheduled_at descending.
    """
    with Session(_get_engine()) as session:
        statement = (
            select(PostRecord)
            .order_by(PostRecord.scheduled_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
        )
        return list(session.exec(statement).all())
