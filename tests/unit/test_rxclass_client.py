import pytest
from pytest_httpx import HTTPXMock
import httpx
from app.infrastructure.rxclass_client import RxClassClient


@pytest.mark.anyio
async def test_get_rxcui_returns_cui_for_known_drug(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://rxnav.nlm.nih.gov/REST/rxcui.json?name=amoxicillin",
        json={"idGroup": {"rxnormId": ["723"]}},
    )

    async with httpx.AsyncClient() as client:
        rxclass = RxClassClient(client)
        result = await rxclass.get_rxcui("amoxicillin")

    assert result == "723"


@pytest.mark.anyio
async def test_get_rxcui_returns_none_on_404(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://rxnav.nlm.nih.gov/REST/rxcui.json?name=unknowndrug",
        status_code=404,
    )

    async with httpx.AsyncClient() as client:
        result = await RxClassClient(client).get_rxcui("unknowndrug")

    assert result is None


@pytest.mark.anyio
async def test_get_epc_classes_returns_typed_epc_classes(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json?rxcui=723&relaSource=DAILYMED",
        json={
            "rxclassDrugInfoList": {
                "rxclassDrugInfo": [
                    {
                        "rxclassMinConceptItem": {
                            "classId": "N0000175503",
                            "className": "Penicillin-class Antibacterial",
                            "classType": "EPC",
                        }
                    },
                ]
            }
        },
    )

    async with httpx.AsyncClient() as client:
        result = await RxClassClient(client).get_epc_classes("723")

    assert len(result) == 1
    assert result[0].class_id == "N0000175503"
    assert result[0].class_name == "Penicillin-class Antibacterial"


@pytest.mark.anyio
async def test_get_epc_classes_filters_out_non_epc_class_types(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json?rxcui=723&relaSource=DAILYMED",
        json={
            "rxclassDrugInfoList": {
                "rxclassDrugInfo": [
                    {
                        "rxclassMinConceptItem": {
                            "classId": "N0000175503",
                            "className": "Penicillin-class Antibacterial",
                            "classType": "EPC",
                        }
                    },
                    {
                        "rxclassMinConceptItem": {
                            "classId": "D000900",
                            "className": "Anti-Bacterial Agents",
                            "classType": "MESHPA",
                        }
                    },
                ]
            }
        },
    )

    async with httpx.AsyncClient() as client:
        result = await RxClassClient(client).get_epc_classes("723")

    assert len(result) == 1
    assert result[0].class_id == "N0000175503"


@pytest.mark.anyio
async def test_get_epc_classes_returns_empty_on_404(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json?rxcui=999&relaSource=DAILYMED",
        status_code=404,
    )

    async with httpx.AsyncClient() as client:
        result = await RxClassClient(client).get_epc_classes("999")

    assert result == []


@pytest.mark.anyio
async def test_get_class_members_returns_typed_members(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://rxnav.nlm.nih.gov/REST/rxclass/classMembers.json?classId=N0000175503&relaSource=DAILYMED&rela=has_epc&ttys=IN",
        json={
            "drugMemberGroup": {
                "drugMember": [
                    {"minConcept": {"rxcui": "723", "name": "amoxicillin"}},
                    {"minConcept": {"rxcui": "18631", "name": "ampicillin"}},
                ]
            }
        },
    )

    async with httpx.AsyncClient() as client:
        result = await RxClassClient(client).get_class_members("N0000175503")

    assert len(result) == 2
    assert result[0].rxcui == "723"
    assert result[0].drug_name == "amoxicillin"


@pytest.mark.anyio
async def test_get_class_members_returns_empty_on_404(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://rxnav.nlm.nih.gov/REST/rxclass/classMembers.json?classId=UNKNOWN&relaSource=DAILYMED&rela=has_epc&ttys=IN",
        status_code=404,
    )

    async with httpx.AsyncClient() as client:
        result = await RxClassClient(client).get_class_members("UNKNOWN")

    assert result == []
