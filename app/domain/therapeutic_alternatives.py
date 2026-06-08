from typing import Protocol

from app.infrastructure.rxclass_client import RxClassClient

# Maps each EPC classId to a list of therapeutically equivalent alternative classIds.
# Sourced from FDA therapeutic equivalence guidelines.
# A prescribed drug's own classId should never appear as a value — the exclusion
# logic in find_alternatives handles that defensively, but the map should not
# encode self-references.
CROSS_CLASS_MAP: dict[str, list[str]] = {}


class DrugRepository(Protocol):
    async def filter_to_cached(self, drug_names: list[str]) -> list[str]: ...


class TherapeuticAlternativeFinder:
    def __init__(self, rxclass: RxClassClient, repo: DrugRepository) -> None:
        self._rxclass = rxclass
        self._repo = repo

    async def find_alternatives(
        self,
        drug_name: str,
        patient_allergies: list[str],
    ) -> list[str]:
        rxcui = await self._rxclass.get_rxcui(drug_name)
        if rxcui is None:
            return []

        epc_classes = await self._rxclass.get_epc_classes(rxcui)
        if not epc_classes:
            return []

        excluded_class_ids: set[str] = set()
        for allergy in patient_allergies:
            allergy_rxcui = await self._rxclass.get_rxcui(allergy)
            if allergy_rxcui:
                allergy_classes = await self._rxclass.get_epc_classes(allergy_rxcui)
                excluded_class_ids.update(c.class_id for c in allergy_classes)

        prescribed_class_ids = {c.class_id for c in epc_classes}

        safe_class_ids = []
        for epc in epc_classes:
            for class_id in CROSS_CLASS_MAP.get(epc.class_id, []):
                if class_id not in excluded_class_ids and class_id not in prescribed_class_ids:
                    safe_class_ids.append(class_id)

        candidate_names = []
        for class_id in safe_class_ids:
            members = await self._rxclass.get_class_members(class_id)
            candidate_names.extend(m.drug_name for m in members)

        if not candidate_names:
            return []

        return await self._repo.filter_to_cached(candidate_names)
