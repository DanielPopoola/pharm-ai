from dataclasses import dataclass

import httpx

from app.core.exceptions import RetryableAPIError
from app.core.retry import retry_with_backoff


@dataclass(frozen=True)
class EpcClass:
    class_id: str
    class_name: str
 
 
@dataclass(frozen=True)
class ClassMember:
    rxcui: str
    drug_name: str


class RxClassClient:
    BASE_URL = "https://rxnav.nlm.nih.gov/REST"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._http = client

    @retry_with_backoff(
        max_retries=3,
        initial_delay=1,
        retry_exceptions=(httpx.RequestError, RetryableAPIError),
    )
    async def get_rxcui(self, drug_name: str) -> str | None:
        response = await self._http.get(
            f"{self.BASE_URL}/rxcui.json",
            params={"name": drug_name},
        )

        if response.status_code == 404:
            return None
        
        if response.status_code in {500, 502, 503}:
            raise RetryableAPIError(f"OpenFDA returned {response.status_code}")
        
        response.raise_for_status()

        ids = (
            response.json()
            .get("idGroup", {})
            .get("rxnormId", [])
        )

        return ids[0] if ids else None

    @retry_with_backoff(
        max_retries=3,
        initial_delay=1,
        retry_exceptions=(httpx.RequestError, RetryableAPIError),
    )   
    async def get_epc_classes(
        self,
        rxcui: str,
    ) -> list[EpcClass]:
        response = await self._http.get(
            f"{self.BASE_URL}/rxclass/class/byRxcui.json",
            params={
                "rxcui": rxcui,
                "relaSource": "DAILYMED",
            },
        )

        if response.status_code == 404:
            return []

        if response.status_code in {500, 502, 503}:
            raise RetryableAPIError(f"OpenFDA returned {response.status_code}")
        
        response.raise_for_status()

        classes = (
            response.json()
            .get("rxclassDrugInfoList", {})
            .get("rxclassDrugInfo", [])
        )

        return [
            EpcClass(
                class_id=item["rxclassMinConceptItem"]["classId"],
                class_name=item["rxclassMinConceptItem"]["className"],
            )
            for item in classes
            if item["rxclassMinConceptItem"]["classType"] == "EPC"
        ]

    @retry_with_backoff(
        max_retries=3,
        initial_delay=1,
        retry_exceptions=(httpx.RequestError, RetryableAPIError),
    )
    async def get_class_members(
        self,
        class_id: str,
    ) -> list[ClassMember]:
        response = await self._http.get(
            f"{self.BASE_URL}/rxclass/classMembers.json",
            params={
                "classId": class_id,
                "relaSource": "DAILYMED",
                "rela": "has_epc",
                "ttys": "IN",
            },
        )

        if response.status_code == 404:
            return []

        if response.status_code in {500, 502, 503}:
            raise RetryableAPIError(f"OpenFDA returned {response.status_code}")
        
        response.raise_for_status()

        concepts = (
            response.json()
            .get("drugMemberGroup", {})
            .get("drugMember", [])
        )

        return [
            ClassMember(
                rxcui=concept["minConcept"]["rxcui"],
                drug_name=concept["minConcept"]["name"],
            )
            for concept in concepts
        ]