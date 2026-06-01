import asyncio
import logging

from google import genai
from google.genai import types

from app.core.config import settings
from app.core.exceptions import RetryableEmbeddingError
from app.core.retry import retry_with_backoff

logger = logging.getLogger("pharmai")

client = genai.Client(api_key=settings.GEMINI_API_KEY)

BATCH_SIZE = settings.EMBEDDING_BATCH_SIZE


async def embed_chunks(texts: list[str]) -> list[list[float]]:
    return await _embed(texts, task_type="RETRIEVAL_DOCUMENT")


async def embed_query(text: str) -> list[float]:
    results = await _embed([text], task_type="RETRIEVAL_QUERY")
    return results[0]


async def _embed(texts: list[str], task_type: str) -> list[list[float]]:
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]

        embeddings = await _embed_batch(batch, task_type)
        all_embeddings.extend(embeddings)

    return all_embeddings


@retry_with_backoff(
    max_retries=3,
    initial_delay=1,
    retry_exceptions=(RetryableEmbeddingError,),
)
async def _embed_batch(batch: list[str], task_type: str):
    try:
        return await asyncio.to_thread(_embed_batch_sync, batch, task_type)

    except Exception as e:
        message = str(e).lower()

        retryable_signals = (
            "rate limit",
            "quota",
            "timeout",
            "temporarily unavailable",
            "503",
            "429",
        )

        if any(sig in message for sig in retryable_signals):
            raise RetryableEmbeddingError(str(e))

        raise


def _embed_batch_sync(batch: list[str], task_type: str):
    response = client.models.embed_content(
        model=settings.GEMINI_EMBEDDING_MODEL,
        contents=batch,
        config=types.EmbedContentConfig(task_type=task_type),
    )
    if response.embeddings:
        return [e.values for e in response.embeddings]
    return []
