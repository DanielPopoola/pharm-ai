from pydantic import BaseModel

from app.ingestion.openfda_client import DrugLabel

CHUNK_SIZE = 400  # words — approximates 512 tokens
OVERLAP = 38
MIN_SECTIONS = 3

SECTION_MAP = {
    "indications_and_usage": "indications_and_usage",
    "dosage_and_administration": "dosage_and_administration",
    "contraindications": "contraindications",
    "warnings_and_precautions": "warnings_and_precautions",
    "drug_interactions": "drug_interactions",
    "description": "description",
}


class DrugChunk(BaseModel):
    drug_name: str
    brand_names: list[str]
    therapeutic_class: str
    section_type: str
    chunk_text: str
    source_url: str


def _chunk_text(text: str) -> list[str]:
    words = text.split()

    if len(words) <= CHUNK_SIZE:
        return [text]

    chunks = []
    start = 0

    while start < len(words):
        end = start + CHUNK_SIZE
        chunks.append(" ".join(words[start:end]))
        start += CHUNK_SIZE - OVERLAP

    return chunks


def parse_label_into_chunks(label: DrugLabel) -> list[DrugChunk]:
    chunks = []

    for field, section_type in SECTION_MAP.items():
        text = getattr(label, field)
        if not text or not text.strip():
            continue

        for chunk_text in _chunk_text(text):
            chunks.append(
                DrugChunk(
                    drug_name=label.drug_name,
                    brand_names=label.brand_names,
                    therapeutic_class=label.therapeutic_class,
                    section_type=section_type,
                    chunk_text=chunk_text,
                    source_url=label.source_url,
                )
            )

    return chunks


def is_clinically_useful(label: DrugLabel) -> bool:
    sections = [
        label.indications_and_usage,
        label.dosage_and_administration,
        label.contraindications,
        label.warnings_and_precautions,
        label.drug_interactions,
        label.description,
    ]
    populated = sum(1 for s in sections if s and s.strip())
    return populated >= MIN_SECTIONS
