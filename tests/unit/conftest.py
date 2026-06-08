import pytest

from unittest.mock import AsyncMock
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
