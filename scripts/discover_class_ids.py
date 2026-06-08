"""
Discover RxClass EPC classIds for all seeded therapeutic classes.

For each class, queries a known representative drug through:
  1. RxNorm /rxcui.json  — drug name → RxCUI
  2. RxClass /class/byRxcui.json — RxCUI → EPC classId + className

Prints a ready-to-paste dict for CROSS_CLASS_MAP in PHARMAI-036.

Usage:
    uv run python scripts/discover_class_ids.py
"""

import asyncio
import json
from pathlib import Path

import httpx

RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"

# One well-known generic drug per seeded therapeutic class.
# The drug only needs to be in RxNorm — it doesn't need to be in our DB.
REPRESENTATIVE_DRUGS: dict[str, str] = {
    "Penicillin-class Antibacterial [EPC]": "amoxicillin",
    "Cephalosporin Antibacterial [EPC]": "cefdinir",
    "Macrolide Antimicrobial [EPC]": "azithromycin",
    "Fluoroquinolone Antibacterial [EPC]": "ciprofloxacin",
    "Tetracycline-class Drug [EPC]": "doxycycline",
    "Angiotensin Converting Enzyme Inhibitor [EPC]": "lisinopril",
    "Angiotensin 2 Receptor Blocker [EPC]": "losartan",
    "Dihydropyridine Calcium Channel Blocker [EPC]": "amlodipine",
    "beta-Adrenergic Blocker [EPC]": "atenolol",
    "Thiazide Diuretic [EPC]": "hydrochlorothiazide",
    "Nonsteroidal Anti-inflammatory Drug [EPC]": "ibuprofen",
    "Opioid Agonist [EPC]": "morphine",
    "Sulfonylurea [EPC]": "glipizide",
    "Insulin Analog [EPC]": "insulin glargine",
    "Anti-coagulant [EPC]": "warfarin",
    "Factor Xa Inhibitor [EPC]": "rivaroxaban",
    "Direct Thrombin Inhibitor [EPC]": "dabigatran",
    "Platelet Aggregation Inhibitor [EPC]": "clopidogrel",
    "HMG-CoA Reductase Inhibitor [EPC]": "atorvastatin",
}


async def get_rxcui(client: httpx.AsyncClient, drug_name: str) -> str | None:
    response = await client.get(
        f"{RXNORM_BASE}/rxcui.json",
        params={"name": drug_name},
    )
    if response.status_code != 200:
        return None
    data = response.json()
    rxcui = data.get("idGroup", {}).get("rxnormId", [])
    return rxcui[0] if rxcui else None


async def get_epc_classes(client: httpx.AsyncClient, rxcui: str) -> list[dict]:
    response = await client.get(
        f"{RXNORM_BASE}/rxclass/class/byRxcui.json",
        params={"rxcui": rxcui, "relaSource": "DAILYMED"},
    )
    if response.status_code != 200:
        return []
    data = response.json()
    classes = (
        data.get("rxclassDrugInfoList", {})
        .get("rxclassDrugInfo", [])
    )
    return [
        {
            "classId": c["rxclassMinConceptItem"]["classId"],
            "className": c["rxclassMinConceptItem"]["className"],
            "classType": c["rxclassMinConceptItem"]["classType"],
        }
        for c in classes
        if c["rxclassMinConceptItem"]["classType"] == "EPC"
    ]


async def main():
    results: dict[str, dict] = {}

    async with httpx.AsyncClient(timeout=10) as client:
        for epc_label, drug_name in REPRESENTATIVE_DRUGS.items():
            print(f"  {epc_label}")

            rxcui = await get_rxcui(client, drug_name)
            if not rxcui:
                print(f"    ✗ No RxCUI found for: {drug_name}")
                results[epc_label] = {"error": "no_rxcui", "drug": drug_name}
                continue

            epc_classes = await get_epc_classes(client, rxcui)

            if not epc_classes:
                print(f"    ✗ No EPC class found for RxCUI {rxcui} ({drug_name})")
                results[epc_label] = {"error": "no_epc_class", "drug": drug_name, "rxcui": rxcui}
                continue

            # Take the first EPC class — representative drugs are single-class
            best = epc_classes[0]
            print(f"    ✓ classId={best['classId']}  className={best['className']}")
            results[epc_label] = {
                "classId": best["classId"],
                "className": best["className"],
                "drug": drug_name,
                "rxcui": rxcui,
            }

    class_id_map = {
        v["classId"]: k
        for k, v in results.items()
        if "classId" in v
    }

    out_path = Path("data/class_ids.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"class_id_map": class_id_map, "full_results": results}, indent=2))
    print(f"\nWrote {len(class_id_map)} class IDs to {out_path}")

    errors = {k: v for k, v in results.items() if "error" in v}
    if errors:
        print(f"{len(errors)} failed lookups:")
        for label, info in errors.items():
            print(f"  {label}: {info['error']}")


asyncio.run(main())