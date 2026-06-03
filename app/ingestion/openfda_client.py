import logging

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import RetryableAPIError
from app.core.retry import retry_with_backoff

logger = logging.getLogger("pharmai")

MAX_OPENFDA_RESULTS = 1000
PAGE_SIZE = 100


class DrugLabel(BaseModel):
    drug_name: str
    brand_names: list[str]
    therapeutic_class: str
    dosage_form: str = "unknown"
    source_url: str
    indications_and_usage: str | None = None
    dosage_and_administration: str | None = None
    contraindications: str | None = None
    warnings_and_precautions: str | None = None
    drug_interactions: str | None = None
    description: str | None = None


def _extract_field(data: dict, field: str) -> str | None:
    value = data.get(field)
    if not value:
        return None
    return " ".join(value) if isinstance(value, list) else value


@retry_with_backoff(
    max_retries=3,
    initial_delay=1,
    retry_exceptions=(
        httpx.RequestError,
        RetryableAPIError,
    ),
)
async def _fetch_page(
    client: httpx.AsyncClient,
    therapeutic_class: str,
    skip: int,
    limit: int,
) -> dict | None:
    params = {
        "search": f'openfda.pharm_class_epc:"{therapeutic_class}"',
        "limit": limit,
        "skip": skip,
    }

    response = await client.get(
        settings.OPENFDA_BASE_URL,
        params=params,
    )

    if response.status_code == 404:
        return {}

    if response.status_code in {429, 500, 502, 503}:
        raise RetryableAPIError(f"OpenFDA returned {response.status_code}")

    response.raise_for_status()
    return response.json()


@retry_with_backoff(
    max_retries=3,
    initial_delay=1,
    retry_exceptions=(
        httpx.RequestError,
        RetryableAPIError,
    ),
)
async def _fetch_drug(
    client: httpx.AsyncClient,
    drug_name: str,
) -> dict | None:
    params = {
        "search": f'openfda.generic_name:"{drug_name}"',
        "limit": 1,
    }

    response = await client.get(
        settings.OPENFDA_BASE_URL,
        params=params,
    )

    if response.status_code == 404:
        return {}

    if response.status_code in {429, 500, 502, 503}:
        raise RetryableAPIError(f"OpenFDA returned {response.status_code}")

    response.raise_for_status()
    return response.json()


def _build_label(
    item: dict,
    therapeutic_class: str,
) -> DrugLabel | None:
    openfda = item.get("openfda", {})
    generic_names = openfda.get("generic_name", [])

    if not generic_names:
        return None

    generic_name = generic_names[0]

    return DrugLabel(
        drug_name=generic_name.lower(),
        brand_names=[name.lower() for name in openfda.get("brand_name", [])],
        therapeutic_class=therapeutic_class,
        source_url=(
            f"{settings.OPENFDA_BASE_URL}?search=openfda.generic_name:{generic_name}"
        ),
        dosage_form=openfda.get("dosage_form", ["unknown"])[0].lower(),
        indications_and_usage=_extract_field(item, "indications_and_usage"),
        dosage_and_administration=_extract_field(item, "dosage_and_administration"),
        contraindications=_extract_field(item, "contraindications"),
        warnings_and_precautions=_extract_field(item, "warnings_and_precautions"),
        drug_interactions=_extract_field(item, "drug_interactions"),
        description=_extract_field(item, "description"),
    )


async def fetch_label_for_drug(
    drug_name: str,
    client: httpx.AsyncClient,
) -> list[DrugLabel]:
    try:
        data = await _fetch_drug(
            client=client,
            drug_name=drug_name,
        )
    except (httpx.RequestError, RetryableAPIError):
        logger.exception("Failed fetching OpenFDA label for drug: %s", drug_name)
        return []

    if not data:
        return []

    results = data.get("results", [])
    if not results:
        return []

    item = results[0]
    openfda = item.get("openfda", {})

    therapeutic_class = openfda.get("pharm_class_epc", ["unknown"])[0]

    label = _build_label(item, therapeutic_class)

    if label:
        logger.info("Fetched label for drug: %s", drug_name)
        return [label]

    return []


def _deduplicate(labels: list[DrugLabel]) -> list[DrugLabel]:
    seen: set[tuple[str, str]] = set()
    unique = []
    for label in labels:
        key = (label.drug_name, label.dosage_form)
        if key not in seen:
            seen.add(key)
            unique.append(label)
    return unique


async def fetch_labels_for_class(
    therapeutic_class: str,
    client: httpx.AsyncClient,
) -> list[DrugLabel]:
    labels: list[DrugLabel] = []
    skip = 0

    while True:
        try:
            data = await _fetch_page(
                client=client,
                therapeutic_class=therapeutic_class,
                skip=skip,
                limit=PAGE_SIZE,
            )
        except (httpx.RequestError, RetryableAPIError):
            logger.exception("Failed fetching OpenFDA page for %s", therapeutic_class)
            break

        if not data:
            break

        results = data.get("results", [])

        for item in results:
            label = _build_label(item, therapeutic_class)
            if label:
                labels.append(label)

        total = data.get("meta", {}).get("results", {}).get("total", 0)
        skip += PAGE_SIZE

        if skip >= min(total, MAX_OPENFDA_RESULTS):
            break

    logger.info("Fetched %d labels for class: %s", len(labels), therapeutic_class)
    labels = _deduplicate(labels)
    logger.info(
        "After deduplication: %d unique labels for class: %s",
        len(labels),
        therapeutic_class,
    )
    return labels
