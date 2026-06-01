import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.ingestion.chunker import DrugChunk
from app.ingestion.openfda_client import DrugLabel

logger = logging.getLogger("pharmai")


def _class_to_filename(therapeutic_class: str) -> str:
    name = therapeutic_class.lower()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    return f"{name}.json"


def _labels_dir() -> Path:
    path = Path(settings.CHECKPOINT_DIR) / "labels"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _embeddings_dir() -> Path:
    path = Path(settings.CHECKPOINT_DIR) / "embeddings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def labels_exist(therapeutic_class: str) -> bool:
    return (_labels_dir() / _class_to_filename(therapeutic_class)).exists()


def write_labels(therapeutic_class: str, labels: list[DrugLabel]) -> None:
    path = _labels_dir() / _class_to_filename(therapeutic_class)
    payload = {
        "therapeutic_class": therapeutic_class,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "labels": [label.model_dump() for label in labels],
    }
    path.write_text(json.dumps(payload, indent=2))
    logger.info("Wrote %d labels checkpoint for: %s", len(labels), therapeutic_class)


def read_labels(therapeutic_class: str) -> list[DrugLabel]:
    path = _labels_dir() / _class_to_filename(therapeutic_class)
    payload = json.loads(path.read_text())
    return [DrugLabel(**label) for label in payload["labels"]]


def embeddings_exist(therapeutic_class: str) -> bool:
    return (_embeddings_dir() / _class_to_filename(therapeutic_class)).exists()


def write_embeddings(
    therapeutic_class: str,
    chunks_with_embeddings: list[tuple[DrugLabel, DrugChunk, list[float]]],
) -> None:
    path = _embeddings_dir() / _class_to_filename(therapeutic_class)

    drugs: dict[str, dict] = {}
    for label, chunk, embedding in chunks_with_embeddings:
        if label.drug_name not in drugs:
            drugs[label.drug_name] = {
                "drug_name": label.drug_name,
                "brand_names": label.brand_names,
                "therapeutic_class": label.therapeutic_class,
                "source_url": label.source_url,
                "chunks": [],
            }
        drugs[label.drug_name]["chunks"].append(
            {
                "section_type": chunk.section_type,
                "chunk_text": chunk.chunk_text,
                "embedding": embedding,
            }
        )

    payload = {
        "therapeutic_class": therapeutic_class,
        "embedded_at": datetime.now(timezone.utc).isoformat(),
        "drugs": list(drugs.values()),
    }
    path.write_text(json.dumps(payload))
    logger.info(
        "Wrote embeddings checkpoint for: %s (%d drugs)",
        therapeutic_class,
        len(drugs),
    )


def read_embeddings(therapeutic_class: str) -> list[dict]:
    path = _embeddings_dir() / _class_to_filename(therapeutic_class)
    payload = json.loads(path.read_text())
    return payload["drugs"]


def wipe_checkpoints() -> None:
    for path in Path(settings.CHECKPOINT_DIR).rglob("*.json"):
        path.unlink()
    logger.info("Wiped all checkpoint files")
