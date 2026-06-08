from typing import Protocol


class SafetyRepository(Protocol):
    async def get_safety_chunks(
        self,
        drug_names: list[str],
    ) -> dict[str, list[str]]: ...


class PatientSafetyScreener:
    def __init__(self, repo: SafetyRepository) -> None:
        self._repo = repo

    async def screen(
        self,
        candidates: list[str],
        patient_allergies: list[str],
        patient_conditions: list[str],
    ) -> dict[str, list[str]]:
        if not patient_allergies and not patient_conditions:
            return {}

        return await self._repo.get_safety_chunks(candidates)
