import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

import logfire
from google import genai
from pydantic_ai import RunContext

from app.agent.models import AlternativeDrug, DrugProfile, PharmAIDeps
from app.core.config import settings
from app.core.logging import setup_llm_observability
from app.retrieval.retrieval import (
    get_drug,
    get_drugs_by_class,
    get_drugs_by_names,
    hybrid_search,
    is_drug_cached,
)

T = TypeVar("T")


setup_llm_observability()

PROFILE_SECTION_TYPES = [
    "indications_and_usage",
    "warnings_and_precautions",
    "dosage_and_administration",
]

ALTERNATIVE_SECTION_TYPES = [
    "indications_and_usage",
    "dosage_and_administration",
]

CONTRAINDICATION_SECTION_TYPES = [
    "contraindications",
    "warnings_and_precautions",
    "drug_interactions",
]

MAX_ALTERNATIVES = 5


async def _traced_call(
    span_name: str,
    fn: Callable[..., Coroutine[Any, Any, T]],
    *args: Any,
    **kwargs: Any,
) -> T:
    with logfire.span(span_name, **{k: v for k, v in kwargs.items() if isinstance(v, (str, int))}):
        return await fn(*args, **kwargs)


async def _summarise_chunks(drug_name: str, chunks: list[str]) -> str:
    prompt = (
        f"Write a 2-3 sentence clinical summary of {drug_name} "
        f"grounded only in the following FDA label excerpts. "
        f"Do not add information not present in the text.\n\n" + "\n\n".join(chunks[:3])
    )
    async with genai.Client(api_key=settings.GEMINI_API_KEY).aio as aclient:
        response = await aclient.models.generate_content(
            model=settings.GEMINI_LLM_MODEL,
            contents=prompt,
        )
    return response.text or ""


async def lookup_drug(ctx: RunContext[PharmAIDeps]) -> DrugProfile | str:
    """
    Retrieve the requested drug's FDA label profile from the local store.
    Use this first for every pharmacist query. If this returns a string, treat it as a cache miss —
    tell the user the drug is not available yet and do not call find_similar_drugs.
    Use the retrieved chunks to write the summary field in the final DrugResponse.
    """
    with logfire.span("tool.lookup_drug", drug_name=ctx.deps.drug_name):
        drug_name = ctx.deps.drug_name

        cached = await _traced_call("cache_check", is_drug_cached, drug_name)
        if not cached:
            return "Drug not found in store. Cache miss triggered."

        drug = await _traced_call("get_drug_metadata", get_drug, drug_name)
        if drug is None:
            return "Drug not found in store. Cache miss triggered."

        chunks = await _traced_call(
            "hybrid_search.profile",
            hybrid_search,
            query=f"{drug_name} indications dosage warnings",
            section_types=PROFILE_SECTION_TYPES,
        )

        summary = await _summarise_chunks(drug_name, [c.chunk_text for c in chunks])

        return DrugProfile(
            drug_name=drug_name,
            brand_names=drug["brand_names"],
            therapeutic_class=drug["therapeutic_class"],
            summary=summary,
        )


async def find_similar_drugs(ctx: RunContext[PharmAIDeps]) -> list[AlternativeDrug]:
    """
    Find therapeutically similar drugs after lookup_drug succeeds.
    Call this only after lookup_drug returns a DrugProfile, then pass results to
    check_contraindications. Return no more than five unique alternatives.
    For each alternative, write a one-sentence rationale comparing its therapeutic
    class to the requested drug. Never leave rationale empty.
    Do not call this after a cache miss.
    """
    with logfire.span("tool.find_similar_drugs", drug_name=ctx.deps.drug_name):
        drug_name = ctx.deps.drug_name

        drug = await _traced_call("get_drug_metadata", get_drug, drug_name)
        if drug is None:
            return []

        candidates = await _traced_call(
            "get_drugs_by_class",
            get_drugs_by_class,
            therapeutic_class=drug["therapeutic_class"],
            exclude_drug=drug_name,
        )

        if not candidates:
            fallback_chunks = await _traced_call(
                "hybrid_search.fallback",
                hybrid_search,
                query=f"{drug_name} therapeutic alternatives indications",
                section_types=["indications_and_usage"],
                exclude_drug=drug_name,
            )

            seen = set()
            candidates = []
            for chunk in fallback_chunks:
                if chunk.drug_name not in seen:
                    seen.add(chunk.drug_name)
                    candidates.append({"drug_name": chunk.drug_name})

        candidate_names = [c["drug_name"] for c in candidates[:MAX_ALTERNATIVES]]

        with logfire.span("get_drugs_by_names_batch", count=len(candidate_names)):
            candidate_drugs = await get_drugs_by_names(candidate_names)

        search_results = await asyncio.gather(
            *[
                _traced_call(
                    "hybrid_search.alternative",
                    hybrid_search,
                    query=f"{name} indications",
                    section_types=["indications_and_usage"],
                    top_k=2,
                )
                for name in candidate_names
            ]
        )

        rationale_tasks = [
            _summarise_chunks(name, [c.chunk_text for c in chunks])
            for name, chunks in zip(candidate_names, search_results)
        ]
        rationales = await asyncio.gather(*rationale_tasks)

        alternatives = []
        for name, _, rationale in zip(candidate_names, search_results, rationales):
            candidate_drug = candidate_drugs.get(name)
            if candidate_drug is None:
                continue

            alternatives.append(
                AlternativeDrug(
                    drug_name=name,
                    brand_names=candidate_drug["brand_names"],
                    therapeutic_class=candidate_drug["therapeutic_class"],
                    rationale=rationale,
                    cautions=[],
                )
            )

        return alternatives


async def check_contraindications(
    ctx: RunContext[PharmAIDeps],
    alternatives: list[AlternativeDrug],
) -> list[str]:
    """
    Retrieve raw FDA label contraindication, warning, and interaction excerpts for each alternative.
    Call this after find_similar_drugs. The agent must reason over these excerpts against the
    patient allergies and conditions to populate contraindication_flags and alternative cautions.
    Only flag conflicts supported by the retrieved text. If patient has no allergies or conditions,
    return an empty list.
    """
    with logfire.span("tool.check_contraindications", alt_count=len(alternatives)):
        patient_context = [*ctx.deps.patient_allergies, *ctx.deps.patient_conditions]
        if not patient_context:
            return []

        context_query = " ".join(patient_context)

        search_results = await asyncio.gather(
            *[
                _traced_call(
                    "hybrid_search.contraindications",
                    hybrid_search,
                    query=f"{alt.drug_name} contraindications warnings interactions {context_query}",
                    section_types=CONTRAINDICATION_SECTION_TYPES,
                    top_k=3,
                )
                for alt in alternatives
            ]
        )

        seen_flags = set()
        flags = []
        for chunks in search_results:
            for chunk in chunks:
                flag = f"{chunk.drug_name}: {chunk.chunk_text[:300]}"
                if flag not in seen_flags:
                    seen_flags.add(flag)
                    flags.append(flag)

        return flags
