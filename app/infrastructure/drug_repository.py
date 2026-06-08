from sqlalchemy import text

from app.core.database import AsyncSessionLocal


class PostgresDrugRepository:
    async def filter_to_cached(self, drug_names: list[str]) -> list[str]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT drug_name FROM drugs
                    WHERE drug_name = ANY(CAST(:names AS text[]))
                """),
                {"names": drug_names},
            )
            return [row["drug_name"] for row in result.mappings()]

    async def get_drug(self, drug_name: str) -> dict | None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT brand_names, therapeutic_class
                    FROM drugs
                    WHERE drug_name = :drug_name
                    LIMIT 1
                """),
                {"drug_name": drug_name},
            )
            row = result.mappings().first()
            return dict(row) if row else None

    async def get_safety_chunks(
        self,
        drug_names: list[str],
    ) -> dict[str, list[str]]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT drug_name, chunk_text
                    FROM drug_chunks
                    WHERE drug_name = ANY(CAST(:names AS text[]))
                    AND section_type = ANY(ARRAY[
                        'contraindications',
                        'warnings_and_precautions',
                        'drug_interactions'
                    ])
                """),
                {"names": drug_names},
            )
            chunks: dict[str, list[str]] = {}
            for row in result.mappings():
                chunks.setdefault(row["drug_name"], []).append(row["chunk_text"])
            return chunks
