"""Typed application configuration using pydantic-settings."""

import json
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    OPENAI_API_KEY: str = Field(default="")
    GEMINI_API_KEY: str = Field(default="")

    # Models
    GEMINI_MODEL: str = "gemini-2.5-flash"
    WHISPER_MODEL: str = "whisper-1"

    # Limits
    MAX_DURATION_SECONDS: int = 180
    MAX_UPLOAD_MB: int = 50
    MAX_CLAIMS: int = 8

    # Paths
    TEMP_DIR: Path = Path("./tmp")
    CACHE_DIR: Path = Path("./cache")

    # Whisper Filter Settings
    NO_SPEECH_THRESHOLD: float = 0.6
    LOGPROB_THRESHOLD: float = -1.0
    HALLUCINATION_PHRASES: str = (
        "thank you for watching,thanks for watching,subtitles by,amara.org,subscribe to my channel"
    )

    # Phase 4 API Settings
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    RATE_LIMIT_PER_HOUR: int = 5
    JOB_TIMEOUT_SECONDS: int = 180
    CACHE_TTL_HOURS: int = 24

    @property
    def hallucination_phrases_list(self) -> list[str]:
        """Return parsed, lowercase list of hallucination phrases from string or JSON."""
        raw = self.HALLUCINATION_PHRASES.strip().strip('"').strip("'")
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]"):
            try:
                items = json.loads(raw)
                return [str(x).strip().lower() for x in items if str(x).strip()]
            except Exception:
                pass
        return [p.strip().lower() for p in raw.split(",") if p.strip()]

    def ensure_directories(self) -> None:
        """Create necessary temporary and cache directories if they do not exist."""
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def validate_openai_key(self) -> None:
        """Verify that OPENAI_API_KEY is present for transcription."""
        if not self.OPENAI_API_KEY or not self.OPENAI_API_KEY.strip():
            raise ValueError(
                "OPENAI_API_KEY is missing or empty. Please set it in your .env file."
            )


# Global settings instance
settings = Settings()
settings.ensure_directories()
