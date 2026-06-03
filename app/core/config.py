from functools import lru_cache

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: PostgresDsn
    REDIS_URL: str

    LLM_API_KEY: str
    GEMINI_API_KEY: str
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    GEMINI_LLM_MODEL: str = "gemini-2.5-flash-lite"

    OPENFDA_BASE_URL: str = "https://api.fda.gov/drug/label.json"

    SEED_THERAPEUTIC_CLASSES: list[str] = [
        # Antibiotics
        "Penicillin-class Antibacterial [EPC]",
        "Cephalosporin Antibacterial [EPC]",
        "Macrolide Antimicrobial [EPC]",
        "Fluoroquinolone Antibacterial [EPC]",
        "Tetracycline-class Drug [EPC]",
        # Antihypertensives
        "Angiotensin Converting Enzyme Inhibitor [EPC]",
        "Angiotensin 2 Receptor Blocker [EPC]",
        "Dihydropyridine Calcium Channel Blocker [EPC]",
        "beta-Adrenergic Blocker [EPC]",
        "Thiazide Diuretic [EPC]",
        # Analgesics
        "Nonsteroidal Anti-inflammatory Drug [EPC]",
        "Opioid Agonist [EPC]",
        # Antidiabetics
        "Sulfonylurea [EPC]",
        "Insulin Analog [EPC]",
        # Anticoagulants
        "Anti-coagulant [EPC]",
        "Factor Xa Inhibitor [EPC]",
        "Direct Thrombin Inhibitor [EPC]",
        "Platelet Aggregation Inhibitor [EPC]",
        # Statins
        "HMG-CoA Reductase Inhibitor [EPC]",
    ]

    EMBEDDING_DIMENSION: int = 768
    TOP_K_RETRIEVAL: int = 5
    FUZZY_MATCH_THRESHOLD: float = 0.5
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
