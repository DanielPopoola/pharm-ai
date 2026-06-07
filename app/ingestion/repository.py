import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal

logger = logging.getLogger("pharmai")


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
                completed_at = :now,
                error_message = :error
            WHERE id = :id
        """),
        {"id": job_id, "now": datetime.now(timezone.utc), "error": error},
    )
    await session.commit()


async def get_active_job(session: AsyncSession, drug_name: str) -> dict | None:
    result = await session.execute(
        text("""
            SELECT id, status FROM ingestion_jobs
            WHERE drug_name = :drug_name
            AND status IN ('pending', 'running')
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"drug_name": drug_name},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def get_job_status(session: AsyncSession, drug_name: str) -> dict | None:
    result = await session.execute(
        text("""
            SELECT drug_name, status, completed_at
            FROM ingestion_jobs
            WHERE drug_name = :drug_name
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"drug_name": drug_name},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def upsert_drugs_and_chunks(drug: dict) -> int:
    async with AsyncSessionLocal() as session:
        try:
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
                    "drug_name": drug["drug_name"],
                    "brand_names": drug["brand_names"],
                    "therapeutic_class": drug["therapeutic_class"],
                    "source_url": drug["source_url"],
                },
            )

            await session.execute(
                text("""
                DELETE FROM drug_chunks WHERE drug_name = :drug_name
            """),
                {"drug_name": drug["drug_name"]},
            )

            rows = 0
            for chunk in drug["chunks"]:
                await session.execute(
                    text("""
                    INSERT INTO drug_chunks
                        (id, drug_name, section_type, chunk_text, embedding)
                    VALUES
                        (:id, :drug_name, :section_type, :chunk_text, :embedding)
                """),
                    {
                        "id": str(uuid.uuid4()),
                        "drug_name": drug["drug_name"],
                        "section_type": chunk["section_type"],
                        "chunk_text": chunk["chunk_text"],
                        "embedding": str(chunk["embedding"]),
                    },
                )
                rows += 1

            await session.commit()
            return rows

        except Exception:
            await session.rollback()
            raise


def verify_upsert(rows_affected: int, drug: dict) -> bool:
    expected = len(drug["chunks"])
    if rows_affected != expected:
        logger.error(
            "Row count mismatch for %s: expected %d, got %d",
            drug["drug_name"],
            expected,
            rows_affected,
        )
        return False
    return True
