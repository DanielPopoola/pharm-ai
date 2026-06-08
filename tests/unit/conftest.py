import pytest

from unittest.mock import AsyncMock
from app.agent.models import DrugProfile, DrugResponse
from app.infrastructure.rxclass_client import EpcClass, ClassMember


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def repo():
    mock = AsyncMock()
    mock.filter_to_cached.return_value = ["azithromycin", "clarithromycin"]
    mock.get_safety_chunks.return_value = {
        "amoxicillin": ["amoxicillin is contraindicated in penicillin allergy"],
        "ampicillin": ["ampicillin is contraindicated in penicillin allergy"],
    }
    mock.get_drug.return_value = {
        "brand_names": ["amoxil"],
        "therapeutic_class": "Penicillin-class Antibacterial [EPC]",
    }
    return mock


@pytest.fixture
def rxclass():
    mock = AsyncMock()
    mock.get_rxcui.return_value = "723"
    mock.get_epc_classes.return_value = [
        EpcClass(class_id="N0000175503", class_name="Penicillin-class Antibacterial")
    ]
    mock.get_class_members.return_value = [
        ClassMember(rxcui="174742", drug_name="azithromycin"),
        ClassMember(rxcui="9524", drug_name="clarithromycin"),
    ]
    return mock


@pytest.fixture
def finder():
    mock = AsyncMock()
    mock.find_alternatives.return_value = ["azithromycin", "clarithromycin"]
    return mock


@pytest.fixture
def screener():
    mock = AsyncMock()
    mock.screen.return_value = {
        "azithromycin": ["azithromycin is contraindicated in liver disease"],
    }
    return mock


@pytest.fixture
def llm():
    mock = AsyncMock()
    mock.return_value = DrugResponse(
        requested_drug=DrugProfile(
            drug_name="amoxicillin",
            brand_names=["amoxil"],
            therapeutic_class="Penicillin-class Antibacterial [EPC]",
            summary="A penicillin-class antibiotic.",
        ),
        alternatives=[],
        contraindication_flags=[],
        clinical_caveats=[],
        cache_miss=False,
    )
    return mock
