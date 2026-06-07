import httpx

from app.agent.models import DrugProfile, DrugResponse
from app.ingestion.openfda_client import fetch_label_for_drug


async def build_degraded_response(drug_name: str) -> DrugResponse:
    async with httpx.AsyncClient(timeout=10) as client:
        labels = await fetch_label_for_drug(drug_name, client)

    if labels:
        label = labels[0]
        profile = DrugProfile(
            drug_name=label.drug_name,
            brand_names=label.brand_names,
            therapeutic_class=label.therapeutic_class,
            summary=label.indications_and_usage or "No summary available.",
        )
    else:
        profile = DrugProfile(
            drug_name=drug_name,
            brand_names=[],
            therapeutic_class="unknown",
            summary="No data available from OpenFDA.",
        )

    return DrugResponse(
        requested_drug=profile,
        alternatives=[],
        clinical_caveats=[
            "This drug is being indexed. Full similarity search will be available shortly. \
            Basic information shown below."
        ],
        cache_miss=True,
    )
