from unittest.mock import AsyncMock, patch
import pytest

from app.domain.therapeutic_alternatives import TherapeuticAlternativeFinder
from app.infrastructure.rxclass_client import ClassMember, EpcClass


@pytest.mark.anyio
async def test_returns_alternatives_for_drug_with_no_allergies(rxclass, repo):
    with patch(
        "app.domain.therapeutic_alternatives.CROSS_CLASS_MAP",
        {"N0000175503": ["N0000175505"]},  # penicillin → macrolide
    ):
        finder = TherapeuticAlternativeFinder(rxclass=rxclass, repo=repo)
        result = await finder.find_alternatives("amoxicillin", patient_allergies=[])

    assert "azithromycin" in result
    assert "clarithromycin" in result


@pytest.mark.anyio
async def test_excludes_prescribed_class_when_patient_is_allergic(rxclass, repo):
    rxclass.get_epc_classes.side_effect = [
        [
            EpcClass(class_id="N0000175503", class_name="Penicillin-class Antibacterial")
        ],  # amoxicillin lookup
        [
            EpcClass(class_id="N0000175503", class_name="Penicillin-class Antibacterial")
        ],  # penicillin allergy lookup
    ]

    with patch(
        "app.domain.therapeutic_alternatives.CROSS_CLASS_MAP",
        {"N0000175503": ["N0000175503", "N0000175505"]},  # maps to itself + macrolide
    ):
        finder = TherapeuticAlternativeFinder(rxclass=rxclass, repo=repo)
        await finder.find_alternatives(
            "amoxicillin",
            patient_allergies=["penicillin"],
        )

    called_class_ids = [call.args[0] for call in rxclass.get_class_members.call_args_list]
    assert "N0000175503" not in called_class_ids
    assert "N0000175505" in called_class_ids


@pytest.mark.anyio
async def test_returns_empty_when_drug_has_no_rxcui(rxclass, repo):
    rxclass.get_rxcui.return_value = None

    finder = TherapeuticAlternativeFinder(rxclass=rxclass, repo=repo)
    result = await finder.find_alternatives("unknowndrug", patient_allergies=[])

    assert result == []
    rxclass.get_epc_classes.assert_not_called()


@pytest.mark.anyio
async def test_returns_empty_when_all_mapped_classes_are_excluded(rxclass, repo):
    rxclass.get_epc_classes.side_effect = [
        [EpcClass(class_id="N0000175503", class_name="Penicillin-class Antibacterial")],  # amoxicillin
        [EpcClass(class_id="N0000175505", class_name="Macrolide Antimicrobial")],  # azithromycin allergy
    ]

    with patch(
        "app.domain.therapeutic_alternatives.CROSS_CLASS_MAP",
        {"N0000175503": ["N0000175505"]},  # only mapped alternative is also excluded
    ):
        finder = TherapeuticAlternativeFinder(rxclass=rxclass, repo=repo)
        result = await finder.find_alternatives(
            "amoxicillin",
            patient_allergies=["azithromycin"],
        )

    assert result == []
    rxclass.get_class_members.assert_not_called()


@pytest.mark.anyio
async def test_filters_to_only_db_cached_drugs(rxclass, repo):
    rxclass.get_epc_classes.return_value = [
        EpcClass(class_id="N0000175503", class_name="Penicillin-class Antibacterial")
    ]
    rxclass.get_class_members.return_value = [
        ClassMember(rxcui="174742", drug_name="azithromycin"),
        ClassMember(rxcui="9524", drug_name="clarithromycin"),
        ClassMember(rxcui="9999", drug_name="telithromycin"),
    ]
    repo.filter_to_cached.return_value = ["azithromycin"]  # only one is in DB

    with patch(
        "app.domain.therapeutic_alternatives.CROSS_CLASS_MAP",
        {"N0000175503": ["N0000175505"]},
    ):
        finder = TherapeuticAlternativeFinder(rxclass=rxclass, repo=repo)
        result = await finder.find_alternatives("amoxicillin", patient_allergies=[])

    assert result == ["azithromycin"]
    repo.filter_to_cached.assert_called_once_with(["azithromycin", "clarithromycin", "telithromycin"])
