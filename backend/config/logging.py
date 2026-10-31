import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Emit compact structured logs without adding request or environment data."""

    def format(self, record):
        event = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event, ensure_ascii=True, separators=(",", ":"))
