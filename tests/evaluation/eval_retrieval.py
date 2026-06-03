import asyncio
import json
from pathlib import Path


from app.retrieval.retrieval import hybrid_search


GOLDEN_PATH = Path("tests/evaluation/retrieval_golden.json")



def precision_at_k(results, expected_drugs, expected_sections):
    relevant = sum(
        1 for r in results
        if r.drug_name in expected_drugs
        and r.section_type in expected_sections
    )
    return relevant / len(results) if results else 0.0

def recall_at_k(results, expected_drugs, expected_sections):
    found_drugs = {
        r.drug_name for r in results
        if r.drug_name in expected_drugs
        and r.section_type in expected_sections
    }
    return len(found_drugs) / len(expected_drugs) if expected_drugs else 0.0


async def main():
    golden = json.loads(GOLDEN_PATH.read_text())

    per_query = []

    for entry in golden:
        results = await hybrid_search(
            query=entry["query"],
            top_k=entry["top_k"],
            section_types=entry["expected_sections"],
        )

        p = precision_at_k(results, entry["expected_drugs"], entry["expected_sections"])
        r = recall_at_k(results, entry["expected_drugs"], entry["expected_sections"])

        per_query.append({
            "query": entry["query"],
            "expected_drugs": entry["expected_drugs"],
            "precision": round(p, 3),
            "recall": round(r, 3),
        })

    print("\nRetrieval Evaluation Report")
    print("=" * 60)

    for q in per_query:
        status = "✓" if q["precision"] > 0.5 and q["recall"] > 0.5 else "✗"
        print(f"\n{status} {q['query']}")
        print(f"  expected : {q['expected_drugs']}")
        print(f"  precision: {q['precision']} | recall: {q['recall']}")

    avg_precision = sum(q["precision"] for q in per_query) / len(per_query)
    avg_recall = sum(q["recall"] for q in per_query) / len(per_query)

    print("\n" + "=" * 60)
    print(f"Average precision : {avg_precision:.3f}")
    print(f"Average recall    : {avg_recall:.3f}")
    print(f"Queries evaluated : {len(per_query)}")
    print(f"Failing queries   : {sum(1 for q in per_query if q['precision'] <= 0.5 or q['recall'] <= 0.5)}")


asyncio.run(main())