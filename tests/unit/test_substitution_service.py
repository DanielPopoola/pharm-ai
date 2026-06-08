import pytest
from unittest.mock import AsyncMock

from app.agent.models import DrugResponse
from app.application.substitution_service import SubstitutionService


@pytest.mark.anyio
async def test_run_returns_full_drug_response_on_cache_hit(finder, screener, repo, llm):
    service = SubstitutionService(finder=finder, screener=screener, repo=repo, llm=llm)
    result = await service.run(
        drug_name="amoxicillin",
        patient_allergies=["penicillin"],
        patient_conditions=["strep throat"],
    )

    assert isinstance(result, DrugResponse)
    assert result.cache_miss is False
    assert result.requested_drug.drug_name == "amoxicillin"
    finder.find_alternatives.assert_called_once_with("amoxicillin", ["penicillin"])
    screener.screen.assert_called_once_with(
        ["azithromycin", "clarithromycin"], ["penicillin"], ["strep throat"]
    )
    llm.assert_called_once()


@pytest.mark.anyio
async def test_run_returns_degraded_response_on_cache_miss(finder, screener, repo, llm):
    repo.get_drug.return_value = None

    service = SubstitutionService(finder=finder, screener=screener, repo=repo, llm=llm)
    result = await service.run(
        drug_name="unknowndrug",
        patient_allergies=[],
        patient_conditions=[],
    )

    assert result.cache_miss is True
    assert result.alternatives == []
    finder.find_alternatives.assert_not_called()
    screener.screen.assert_not_called()
    llm.assert_not_called()
