import asyncio
import random
from functools import wraps
from typing import Callable, TypeVar

T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    retry_exceptions: tuple[type[Exception], ...] = (Exception,),
):
    def decorator(func: Callable[..., T]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except retry_exceptions as exc:
                    last_exception = exc

                    if attempt == max_retries - 1:
                        raise

                    delay = initial_delay * (2**attempt) + random.uniform(0, 1)

                    await asyncio.sleep(delay)

            raise last_exception

        return wrapper

    return decorator
