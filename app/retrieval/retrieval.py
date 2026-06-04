import asyncio
from dataclasses import dataclass

from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.ingestion.embedder import embed_query


@dataclass(frozen=True)
class RetrievedChunk:
    drug_name: str
    section_type: str
    chunk_text: str
    score: float


async def semantic_search(
    query: str,
    top_k: int = settings.TOP_K_RETRIEVAL,
    section_types: list[str] | None = None,
    exclude_drug: str | None = None,
) -> list[RetrievedChunk]:
    query_embeddings = await embed_query(query)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT drug_name, section_type, chunk_text,
                       1 - (embedding <=> CAST(:query_vec AS vector)) AS score
                FROM drug_chunks
                WHERE (CAST(:section_types AS text[]) IS NULL
                    OR section_type = ANY(CAST(:section_types AS text[])))
                AND (CAST(:exclude_drug AS text) IS NULL OR drug_name != :exclude_drug)
                ORDER BY embedding <=> CAST(:query_vec AS vector)
                LIMIT :top_k
            """),
            {
                "query_vec": str(query_embeddings),
                "section_types": section_types,
                "exclude_drug": exclude_drug,
                "top_k": top_k,
            },
        )

    return [
        RetrievedChunk(
            drug_name=row["drug_name"],
            section_type=row["section_type"],
            chunk_text=row["chunk_text"],
            score=float(row["score"]),
        )
        for row in result.mappings()
    ]


async def lexical_search(
    query: str,
    top_k: int = settings.TOP_K_RETRIEVAL,
    section_types: list[str] | None = None,
    exclude_drug: str | None = None,
) -> list[RetrievedChunk]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT drug_name, section_type, chunk_text,
                       ts_rank(to_tsvector('english', chunk_text),
                               plainto_tsquery('english', :query)) AS score
                FROM drug_chunks
                WHERE to_tsvector('english', chunk_text)
                      @@ plainto_tsquery('english', :query)
                  AND (CAST(:section_types AS text[]) IS NULL
                       OR section_type = ANY(CAST(:section_types AS text[])))
                  AND (CAST(:exclude_drug AS text) IS NULL OR drug_name != :exclude_drug)
                ORDER BY score DESC
                LIMIT :top_k
            """),
            {
                "query": query,
                "section_types": section_types,
                "exclude_drug": exclude_drug,
                "top_k": top_k,
            },
        )

    return [
        RetrievedChunk(
            drug_name=row["drug_name"],
            section_type=row["section_type"],
            chunk_text=row["chunk_text"],
            score=float(row["score"]),
        )
        for row in result.mappings()
    ]


async def hybrid_search(
    query: str,
    top_k: int = settings.TOP_K_RETRIEVAL,
    section_types: list[str] | None = None,
    exclude_drug: str | None = None,
    lexical_only: bool = False,
) -> list[RetrievedChunk]:
    if lexical_only:
        return await lexical_search(
            query=query, top_k=top_k, section_types=section_types, exclude_drug=exclude_drug
        )

    semantic_results, lexical_results = await asyncio.gather(
        semantic_search(
            query=query, top_k=top_k, section_types=section_types, exclude_drug=exclude_drug
        ),
        lexical_search(query=query, top_k=top_k, section_types=section_types, exclude_drug=exclude_drug),
    )

    scores: dict[tuple[str, str, str], float] = {}
    for rank, chunk in enumerate(semantic_results):
        key = (chunk.drug_name, chunk.section_type, chunk.chunk_text)
        scores[key] = scores.get(key, 0.0) + 1 / (60 + rank)

    for rank, chunk in enumerate(lexical_results):
        key = (chunk.drug_name, chunk.section_type, chunk.chunk_text)
        scores[key] = scores.get(key, 0.0) + 1 / (60 + rank)

    ranked_chunks = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [
        RetrievedChunk(
            drug_name=drug_name,
            section_type=section_type,
            chunk_text=chunk_text,
            score=score,
        )
        for (drug_name, section_type, chunk_text), score in ranked_chunks[:top_k]
    ]


async def get_drug(drug_name: str) -> dict | None:
    async with AsyncSessionLocal() as session:
        exact_result = await session.execute(
            text("""
                SELECT brand_names, therapeutic_class
                FROM drugs
                WHERE drug_name = :drug_name
                LIMIT 1
            """),
            {"drug_name": drug_name},
        )
        exact_row = exact_result.mappings().first()
        if exact_row is not None:
            return dict(exact_row)

        fuzzy_result = await session.execute(
            text("""
                SELECT brand_names, therapeutic_class
                FROM drugs
                WHERE similarity(drug_name, :drug_name) > :threshold
                ORDER BY similarity(drug_name, :drug_name) DESC
                LIMIT 1
            """),
            {"drug_name": drug_name, "threshold": settings.FUZZY_MATCH_THRESHOLD},
        )
        fuzzy_row = fuzzy_result.mappings().first()
        return dict(fuzzy_row) if fuzzy_row is not None else None


async def get_drugs_by_class(therapeutic_class: str, exclude_drug: str) -> list[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT drug_name, therapeutic_class, brand_names
                FROM drugs
                WHERE therapeutic_class = :therapeutic_class
                AND drug_name != :exclude_drug
            """),
            {"therapeutic_class": therapeutic_class, "exclude_drug": exclude_drug},
        )
        return [dict(row) for row in result.mappings()]


async def get_drugs_by_names(drug_names: list[str]) -> dict[str, dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT drug_name, brand_names, therapeutic_class
                FROM drugs
                WHERE drug_name = ANY(CAST(:names AS text[]))
            """),
            {"names": drug_names},
        )
        return {row["drug_name"]: dict(row) for row in result.mappings()}


async def is_drug_cached(name: str) -> bool:
    async with AsyncSessionLocal() as session:
        exact_result = await session.execute(
            text("""
                SELECT 1 FROM drugs WHERE drug_name = :name LIMIT 1
            """),
            {"name": name},
        )
        if exact_result.scalar_one_or_none() is not None:
            return True

        fuzzy_result = await session.execute(
            text("""
                SELECT 1
                FROM drugs
                WHERE similarity(drug_name, :name) > :threshold
                LIMIT 1
            """),
            {"name": name, "threshold": settings.FUZZY_MATCH_THRESHOLD},
        )
        return fuzzy_result.scalar_one_or_none() is not None
