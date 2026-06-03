import asyncio
from app.retrieval.retrieval import semantic_search, lexical_search, hybrid_search, is_drug_cached

async def main():
    print("=== semantic search ===")
    results = await hybrid_search("bacterial throat infection treatment", top_k=3)
    for r in results:
        print(f"{r.drug_name} | {r.section_type} | score={r.score:.4f}")
        print(f"  {r.chunk_text[:100]}...")
        print()

    print("=== cache check ===")
    print(await is_drug_cached("ciprofloxacin"))   # should be True
    print(await is_drug_cached("ibuprofen"))        # should be False  
    print(await is_drug_cached("ciprofloxaci"))     # typo — fuzzy should catch it
asyncio.run(main())