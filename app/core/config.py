from functools import lru_cache

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: PostgresDsn
    REDIS_URL: str

    GEMINI_API_KEY: str
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"
    GEMINI_LLM_MODEL: str = "gemini-2.5-flash-lite"

    OPENFDA_BASE_URL: str = "https://api.fda.gov/drug/label.json"

    SEED_THERAPEUTIC_CLASSES: list[str] = [
        "antibiotic",
        "antihypertensive",
        "analgesic",
        "antidiabetic",
        "anticoagulant",
        "statin",
    ]

    EMBEDDING_DIMENSION: int = 768
    TOP_K_RETRIEVAL: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings  # type: ignore[call-arg]


settings = get_settings()
