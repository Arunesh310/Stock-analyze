"""Application configuration loaded from environment variables / .env file."""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


CsvList = Annotated[List[str], NoDecode]


class Settings(BaseSettings):
    """Centralised settings."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    environment: str = "development"
    cors_origins: CsvList = Field(default_factory=lambda: ["http://localhost:3000"])

    # Database
    database_url: str = "sqlite:///./app.db"

    # Vector store
    chroma_dir: str = "./chroma_store"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout: int = 120

    # Market data
    default_indices: CsvList = Field(
        default_factory=lambda: ["^NSEI", "^NSEBANK", "^INDIAVIX"]
    )
    default_fx: CsvList = Field(default_factory=lambda: ["INR=X"])
    default_commodities: CsvList = Field(default_factory=lambda: ["CL=F", "GC=F"])
    cache_ttl_seconds: int = 60

    # News (RSS list)
    news_feeds: CsvList = Field(
        default_factory=lambda: [
            "https://www.moneycontrol.com/rss/MCtopnews.xml",
            "https://www.livemint.com/rss/markets",
            "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
            "https://www.business-standard.com/rss/markets-106.rss",
        ]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator(
        "cors_origins", "default_indices", "default_fx",
        "default_commodities", "news_feeds",
        mode="before",
    )
    @classmethod
    def _split_csv(cls, v):
        """Allow comma-separated env strings (or python lists) for list fields."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalise_db_url(cls, v):
        """Neon (and some other managed Postgres providers) hand out
        ``postgres://...`` URLs. SQLAlchemy 2.x only accepts ``postgresql://``
        so we rewrite the scheme transparently — this means a user can paste
        either form into the Render env var and it just works.
        """
        if isinstance(v, str) and v.startswith("postgres://"):
            return "postgresql://" + v[len("postgres://") :]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
