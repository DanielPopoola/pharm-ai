import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def create_job(session: AsyncSession, drug_name: str, triggered_by: str) -> str:
    job_id = str(uuid.uuid4())

    await session.execute(
        text("""
            INSERT INTO ingestion_jobs (id, drug_name, status, triggered_by)
            VALUES (:id, :drug_name, 'running', :triggered_by)
        """),
        {
            "id": job_id,
            "drug_name": drug_name,
            "triggered_by": triggered_by,
        },
    )

    await session.commit()
    return job_id


async def complete_job(session: AsyncSession, job_id: str):
    await session.execute(
        text("""
            UPDATE ingestion_jobs
            SET status = 'complete',
                completed_at = :now
            WHERE id = :id
        """),
        {"id": job_id, "now": datetime.now(timezone.utc)},
    )

    await session.commit()


async def fail_job(session: AsyncSession, job_id: str, error: str):
    await session.execute(
        text("""
            UPDATE ingestion_jobs
            SET status = 'failed',
                completed_at = :now
            WHERE id = :id
        """),
        {"id": job_id, "now": datetime.now(timezone.utc)},
    )

    await session.commit()


async def upsert_drugs_and_chunks(session, chunks, embeddings):
    # --- upsert drugs ---
    seen = {}

    for label, _ in chunks:
        seen[label.drug_name] = label

    for label in seen.values():
        await session.execute(
            text("""
                INSERT INTO drugs
                (id, drug_name, brand_names, therapeutic_class, source_url)
                VALUES (:id, :drug_name, :brand_names, :therapeutic_class, :source_url)
                ON CONFLICT (drug_name) DO UPDATE SET
                    brand_names = EXCLUDED.brand_names,
                    therapeutic_class = EXCLUDED.therapeutic_class,
                    ingested_at = now()
            """),
            {
                "id": str(uuid.uuid4()),
                "drug_name": label.drug_name,
                "brand_names": label.brand_names,
                "therapeutic_class": label.therapeutic_class,
                "source_url": label.source_url,
            },
        )

    # --- delete old chunks ---
    for drug_name in seen:
        await session.execute(
            text("DELETE FROM drug_chunks WHERE drug_name = :drug_name"),
            {"drug_name": drug_name},
        )

    # --- insert new chunks ---
    for (label, chunk), embedding in zip(chunks, embeddings):
        await session.execute(
            text("""
                INSERT INTO drug_chunks (
                    id,
                    drug_name,
                    section_type,
                    chunk_text,
                    embedding
                )
                VALUES (
                    :id,
                    :drug_name,
                    :section_type,
                    :chunk_text,
                    :embedding
                )
            """),
            {
                "id": str(uuid.uuid4()),
                "drug_name": chunk.drug_name,
                "section_type": chunk.section_type,
                "chunk_text": chunk.chunk_text,
                "embedding": str(embedding),
            },
        )

    await session.commit()
