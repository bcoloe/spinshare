# backend/app/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    SPOTIFY_CLIENT_ID: str = ""
    SPOTIFY_CLIENT_SECRET: str = ""
    SPOTIFY_REDIRECT_URI: str = ""
    FRONTEND_URL: str = "http://localhost:5173"
    # ── Email ────────────────────────────────────────────────────────────────
    # SMTP_ENABLED gates all outbound email (false = log-only, useful in dev).
    SMTP_ENABLED: bool = False
    # EMAIL_PROVIDER selects the delivery backend: "resend" (default) or "smtp".
    EMAIL_PROVIDER: str = "resend"
    EMAIL_FROM: str = "noreply@spinshare.app"
    # Resend settings (used when EMAIL_PROVIDER="resend")
    RESEND_API_KEY: str = ""
    # SMTP settings (used when EMAIL_PROVIDER="smtp")
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USE_TLS: bool = True
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@spinshare.app"  # kept for backward compat
    APPLE_MUSIC_TEAM_ID: str = ""
    APPLE_MUSIC_KEY_ID: str = ""
    APPLE_MUSIC_PRIVATE_KEY: str = ""
    # ── GitHub Feedback ──────────────────────────────────────────────────────
    # GITHUB_TOKEN is a personal access token with repo/issues write scope.
    # GITHUB_REPO is the target repository in "owner/repo" format.
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = ""  # e.g. "myorg/spinshare"

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


def get_settings(env_file: str | None = None) -> Settings:
    if env_file:
        return Settings(_env_file=env_file)
    return Settings()
