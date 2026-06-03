import asyncio

from pydantic_ai.exceptions import ModelHTTPError

from app.core.logging import setup_llm_observability
from app.agent.agent import agent
from app.agent.models import PharmAIDeps


setup_llm_observability()

async def main():
    deps = PharmAIDeps(
        drug_name="atenolol",
        patient_allergies=["beta blockers"],
        patient_conditions=["asthma", "heart failure"],
    )

    try:
        result = await agent.run(
            "What are the therapeutic alternatives for atenolol?",
            deps=deps,
        )
        print(result.output.model_dump_json(indent=2))
    except ModelHTTPError as e:
        if e.status_code == 429:
            print("Rate limit hit — wait a moment and retry.")
        else:
            print(f"Model error {e.status_code}: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


asyncio.run(main())
