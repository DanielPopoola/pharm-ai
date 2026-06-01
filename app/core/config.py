from functools import lru_cache

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: PostgresDsn
    REDIS_URL: str

    GEMINI_API_KEY: str
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    GEMINI_LLM_MODEL: str = "gemini-2.5-flash-lite"

    OPENFDA_BASE_URL: str = "https://api.fda.gov/drug/label.json"

    SEED_THERAPEUTIC_CLASSES: list[str] = [
        "Cephalosporin Antibacterial [EPC]",  # antibiotic (count: 78)
        "Macrolide Antimicrobial [EPC]",  # antibiotic (count: 98)
        "Fluoroquinolone Antibacterial [EPC]",  # antibiotic (count: 82)
        "Angiotensin Converting Enzyme Inhibitor [EPC]",  # antihypertensive (count: 65)
        "Angiotensin 2 Receptor Blocker [EPC]",  # antihypertensive (count: 282)
        "beta-Adrenergic Blocker [EPC]",  # antihypertensive (count: 272)
        "Nonsteroidal Anti-inflammatory Drug [EPC]",  # analgesic (count: 2543)
        "Sulfonylurea [EPC]",  # antidiabetic (count: 247)
        "Insulin Analog [EPC]",  # antidiabetic (count: 65)
        "Anti-coagulant [EPC]",  # anticoagulant (count: 136)
        "HMG-CoA Reductase Inhibitor [EPC]",
    ]

    EMBEDDING_DIMENSION: int = 768
    TOP_K_RETRIEVAL: int = 5
    EMBEDDING_BATCH_SIZE: int = 5
    EMBEDDING_RPM_LIMIT: int = 11
    EMBEDDING_REQUESTS_PER_DAY: int = 1000

    CHECKPOINT_DIR: str = "data/checkpoints"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
