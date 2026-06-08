import logging

from google import genai

from app.agent.models import DrugResponse
from app.core.config import settings

logger = logging.getLogger("pharmai")

_client = genai.Client(api_key=settings.GEMINI_API_KEY)

SYSTEM_PROMPT = """
You are PharmAI, a clinical drug reference assistant for pharmacists.

You will receive:
- A prescribed drug name and its metadata
- A list of therapeutic alternative drug names
- FDA label excerpts for each alternative covering contraindications, warnings, and drug interactions
- Patient allergies and conditions

Your task is to return a JSON object that strictly matches this schema:
{
    "requested_drug": {
        "drug_name": string,
        "brand_names": list[string],
        "therapeutic_class": string,
        "summary": string  -- 2-3 sentence clinical summary grounded in FDA label text
    },
    "alternatives": [
        {
            "drug_name": string,
            "brand_names": list[string],
            "therapeutic_class": string,
            "rationale": string,  -- one sentence explaining why this is a relevant alternative
            "cautions": list[string]  -- patient-specific cautions from retrieved text
        }
    ],
    "contraindication_flags": [
        {
            "drug_name": string,
            "condition": string  -- short phrase, max 5 words
        }
    ],
    "clinical_caveats": list[string],
    "cache_miss": false
}

Rules:
- Ground every clinical statement in the retrieved FDA label excerpts provided
- Do not invent indications, dosages, or warnings not present in the retrieved text
- Only populate contraindication_flags when the retrieved text explicitly supports the conflict
- Return ONLY valid JSON — no preamble, no markdown, no backticks
"""


def _build_prompt(
    drug_name: str,
    drug_metadata: dict,
    alternatives: list[str],
    safety_chunks: dict[str, list[str]],
    patient_allergies: list[str],
    patient_conditions: list[str],
) -> str:
    lines = [
        f"Prescribed drug: {drug_name}",
        f"Brand names: {', '.join(drug_metadata.get('brand_names', []))}",
        f"Therapeutic class: {drug_metadata.get('therapeutic_class', 'unknown')}",
        f"Patient allergies: {', '.join(patient_allergies) or 'none'}",
        f"Patient conditions: {', '.join(patient_conditions) or 'none'}",
        "",
        "Therapeutic alternatives:",
        *[f"- {name}" for name in alternatives],
        "",
        "FDA label excerpts per alternative:",
    ]

    for drug, chunks in safety_chunks.items():
        lines.append(f"\n{drug}:")
        for chunk in chunks:
            lines.append(f"  {chunk[:300]}")

    return "\n".join(lines)


async def gemini_llm(
    drug_name: str,
    drug_metadata: dict,
    alternatives: list[str],
    safety_chunks: dict[str, list[str]],
    patient_allergies: list[str],
    patient_conditions: list[str],
) -> DrugResponse:
    prompt = _build_prompt(
        drug_name,
        drug_metadata,
        alternatives,
        safety_chunks,
        patient_allergies,
        patient_conditions,
    )

    async with _client.aio as aclient:
        response = await aclient.models.generate_content(
            model=settings.GEMINI_LLM_MODEL,
            contents=prompt,
            config={
                "system_instruction": SYSTEM_PROMPT,
                "response_mime_type": "application/json",
                "response_schema": DrugResponse,
            },
        )

    return DrugResponse.model_validate_json(response.text)
