from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.agent import agent
from app.agent.models import DrugResponse, PharmacistQuery, PharmAIDeps
from app.api.dependencies import build_degraded_response
from app.core.database import get_session
from app.core.logging import setup_logging
from app.ingestion.repository import get_active_job, get_job_status
from app.retrieval.retrieval import is_drug_cached
from app.worker import celery_app

setup_logging()
app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/query", response_model=DrugResponse)
async def query(
    body: PharmacistQuery,
    session: AsyncSession = Depends(get_session),
) -> DrugResponse:
    cached = await is_drug_cached(body.drug_name)

    if not cached:
        active = await get_active_job(session, body.drug_name)
        if not active:
            celery_app.send_task(
                "app.tasks.ingest_drug_on_demand",
                args=[body.drug_name],
            )
        return await build_degraded_response(body.drug_name)

    deps = PharmAIDeps(
        drug_name=body.drug_name,
        patient_allergies=body.patient_allergies,
        patient_conditions=body.patient_conditions,
    )
    result = await agent.run(
        f"Review {body.drug_name} for this patient.",
        deps=deps,
    )
    return result.output


@app.get("/drugs/{drug_name}/ingestion-status")
async def ingestion_status(
    drug_name: str,
    session: AsyncSession = Depends(get_session),
):
    job = await get_job_status(session, drug_name)
    if not job:
        raise HTTPException(status_code=404, detail="No ingestion job found for this drug.")
    return job
