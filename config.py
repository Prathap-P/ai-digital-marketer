"""Application configuration loaded from environment variables / .env file."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROMPTS_DIR = Path(__file__).parent / "prompts"

class Settings(BaseSettings):
    """All runtime settings.  Override any field via environment variable."""

    # ── LinkedIn OAuth 2.0 ──────────────────────────────────────────────────────
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    # Must match the redirect URI registered in your LinkedIn Developer app.
    linkedin_redirect_uri: str = "http://localhost:8000/auth/linkedin/callback"

    # ── Reddit ────────────────────────────────────────────────────────────────
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_username: str = ""
    reddit_password: str = ""
    reddit_default_subreddits: str = "MachineLearning,singularity,technology"


    # ── App ───────────────────────────────────────────────────────────────────
    dry_run: bool = False
    session_ttl_minutes: int = 120
    app_secret_key: str = "change_me_in_production"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def reddit_default_subreddits_list(self) -> list[str]:
        """Return the default subreddits as a parsed list."""
        return [s.strip() for s in self.reddit_default_subreddits.split(",") if s.strip()]

# Module-level singleton — import this everywhere.
settings = Settings()
