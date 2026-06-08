from collections.abc import Awaitable, Callable

from app.agent.models import DrugProfile, DrugResponse
from app.domain.patient_safety import PatientSafetyScreener
from app.domain.therapeutic_alternatives import TherapeuticAlternativeFinder


class SubstitutionService:
    def __init__(
        self,
        finder: TherapeuticAlternativeFinder,
        screener: PatientSafetyScreener,
        repo,
        llm: Callable[..., Awaitable[DrugResponse]],
    ) -> None:
        self._finder = finder
        self._screener = screener
        self._repo = repo
        self._llm = llm

    async def run(
        self,
        drug_name: str,
        patient_allergies: list[str],
        patient_conditions: list[str],
    ) -> DrugResponse:
        drug = await self._repo.get_drug(drug_name)
        if drug is None:
            return DrugResponse(
                requested_drug=DrugProfile(
                    drug_name=drug_name,
                    brand_names=[],
                    therapeutic_class="unknown",
                    summary="Drug not found in store.",
                ),
                cache_miss=True,
            )

        alternatives = await self._finder.find_alternatives(drug_name, patient_allergies)
        safety_chunks = await self._screener.screen(alternatives, patient_allergies, patient_conditions)

        return await self._llm(
            drug_name=drug_name,
            drug_metadata=drug,
            alternatives=alternatives,
            safety_chunks=safety_chunks,
            patient_allergies=patient_allergies,
            patient_conditions=patient_conditions,
        )
