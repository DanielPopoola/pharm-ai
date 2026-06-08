import pytest

from app.domain.patient_safety import PatientSafetyScreener


@pytest.mark.anyio
async def test_returns_empty_dict_when_no_patient_context(repo):
    screener = PatientSafetyScreener(repo=repo)
    result = await screener.screen(
        candidates=["amoxicillin", "ampicillin"],
        patient_allergies=[],
        patient_conditions=[],
    )

    assert result == {}
    repo.get_safety_chunks.assert_not_called()


@pytest.mark.anyio
async def test_returns_chunks_keyed_by_drug_name(repo):
    screener = PatientSafetyScreener(repo=repo)
    result = await screener.screen(
        candidates=["amoxicillin", "ampicillin"],
        patient_allergies=["penicillin"],
        patient_conditions=[],
    )

    assert "amoxicillin" in result
    assert "ampicillin" in result
    assert result["amoxicillin"] == ["amoxicillin is contraindicated in penicillin allergy"]


@pytest.mark.anyio
async def test_passes_all_candidates_in_single_repo_call(repo):
    screener = PatientSafetyScreener(repo=repo)
    await screener.screen(
        candidates=["amoxicillin", "ampicillin", "azithromycin"],
        patient_allergies=["penicillin"],
        patient_conditions=[],
    )

    repo.get_safety_chunks.assert_called_once_with(["amoxicillin", "ampicillin", "azithromycin"])
