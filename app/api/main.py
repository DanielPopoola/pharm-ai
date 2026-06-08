from collections.abc import AsyncGenerator

import httpx
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.models import DrugResponse, PharmacistQuery
from app.api.dependencies import build_degraded_response
from app.application.substitution_service import SubstitutionService
from app.core.database import get_session
from app.core.logging import setup_logging
from app.domain.patient_safety import PatientSafetyScreener
from app.domain.therapeutic_alternatives import TherapeuticAlternativeFinder
from app.infrastructure.drug_repository import PostgresDrugRepository
from app.infrastructure.llm import gemini_llm
from app.infrastructure.rxclass_client import RxClassClient
from app.ingestion.repository import get_active_job, get_job_status
from app.retrieval.retrieval import is_drug_cached
from app.worker import celery_app

setup_logging()
app = FastAPI()


async def get_substitution_service() -> AsyncGenerator[SubstitutionService, None]:
    async with httpx.AsyncClient() as client:
        repo = PostgresDrugRepository()
        finder = TherapeuticAlternativeFinder(
            rxclass=RxClassClient(client),
            repo=repo,
        )
        screener = PatientSafetyScreener(repo=repo)
        yield SubstitutionService(finder=finder, screener=screener, repo=repo, llm=gemini_llm)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/query", response_model=DrugResponse)
async def query(
    body: PharmacistQuery,
    session: AsyncSession = Depends(get_session),
    service: SubstitutionService = Depends(get_substitution_service),
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

    return await service.run(
        drug_name=body.drug_name,
        patient_allergies=body.patient_allergies,
        patient_conditions=body.patient_conditions,
    )


@app.get("/drugs/{drug_name}/ingestion-status")
async def ingestion_status(
    drug_name: str,
    session: AsyncSession = Depends(get_session),
):
    job = await get_job_status(session, drug_name)
    if not job:
        raise HTTPException(status_code=404, detail="No ingestion job found for this drug.")
    return job
