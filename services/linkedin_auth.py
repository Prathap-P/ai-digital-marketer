"""LinkedIn OAuth 2.0 token store — persisted to data/linkedin_token.json.

Only one LinkedIn account is supported at a time.
The token survives server restarts. If the file is missing or corrupt,
the app simply starts in the disconnected state.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_TOKEN_FILE = Path(__file__).parent.parent / "data" / "linkedin_token.json"


@dataclass
class _LinkedInToken:
    access_token: str
    person_id: str
    expires_at: Optional[datetime]


_lock = threading.Lock()
_token: Optional[_LinkedInToken] = None
_pending_state: Optional[str] = None  # CSRF state during OAuth flow


# ── File persistence helpers ───────────────────────────────────────────────

def _save() -> None:
    """Write the current token to disk (must be called with _lock held)."""
    if _token is None:
        _TOKEN_FILE.unlink(missing_ok=True)
        return
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "access_token": _token.access_token,
        "person_id": _token.person_id,
        "expires_at": _token.expires_at.isoformat() if _token.expires_at else None,
    }
    _TOKEN_FILE.write_text(json.dumps(data, indent=2))


def load_token() -> None:
    """Read the token file on startup and populate the in-memory store.

    Safe to call even if the file doesn't exist or is corrupt.
    """
    global _token
    if not _TOKEN_FILE.exists():
        return
    try:
        data = json.loads(_TOKEN_FILE.read_text())
        expires_at: Optional[datetime] = None
        if data.get("expires_at"):
            expires_at = datetime.fromisoformat(data["expires_at"])
            # Discard if already expired
            if expires_at <= datetime.now(timezone.utc):
                logger.warning("Stored LinkedIn token has expired — reconnect required.")
                _TOKEN_FILE.unlink(missing_ok=True)
                return
        with _lock:
            _token = _LinkedInToken(
                access_token=data["access_token"],
                person_id=data["person_id"],
                expires_at=expires_at,
            )
        logger.info("LinkedIn token loaded from disk (person_id=%s).", data["person_id"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load LinkedIn token file: %s", exc)


# ── Public API ──────────────────────────────────────────────────────────────

def set_token(
    access_token: str,
    person_id: str,
    expires_in: Optional[int] = None,
) -> None:
    """Store an OAuth token and persist it to disk."""
    global _token
    expires_at: Optional[datetime] = None
    if expires_in:
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    with _lock:
        _token = _LinkedInToken(
            access_token=access_token,
            person_id=person_id,
            expires_at=expires_at,
        )
        _save()


def get_token() -> Optional[str]:
    """Return the stored access token, or None if not connected."""
    with _lock:
        return _token.access_token if _token else None


def get_person_id() -> Optional[str]:
    """Return the stored LinkedIn person ID (URN fragment), or None."""
    with _lock:
        return _token.person_id if _token else None


def is_connected() -> bool:
    """True when a valid token is held in memory."""
    with _lock:
        return _token is not None


def token_expires_at() -> Optional[datetime]:
    """Return the token expiry time (UTC), or None if unknown / not connected."""
    with _lock:
        return _token.expires_at if _token else None


def disconnect() -> None:
    """Clear the stored token and delete the token file."""
    global _token
    with _lock:
        _token = None
        _save()


# ── CSRF state helpers ─────────────────────────────────────────────────────────

def set_pending_state(state: str) -> None:
    """Store the OAuth `state` parameter generated before the redirect."""
    global _pending_state
    with _lock:
        _pending_state = state


def consume_pending_state() -> Optional[str]:
    """Pop and return the stored state (one-time use)."""
    global _pending_state
    with _lock:
        s = _pending_state
        _pending_state = None
        return s
