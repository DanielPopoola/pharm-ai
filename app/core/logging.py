import json
import logging
from datetime import datetime, timezone

import logfire


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "time": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.module,
            }
        )


def setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def setup_llm_observability() -> None:
    logfire.configure()
    logfire.instrument_pydantic_ai()


logger = logging.getLogger("pharmai")
