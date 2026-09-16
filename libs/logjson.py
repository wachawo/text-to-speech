#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JSON log formatter: one object per line with the record fields plus every extra the caller attached."""

import json
import logging
from datetime import datetime

# Attributes every LogRecord carries; anything else on a record came from `extra=`.
STANDARD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
        "asctime",
    }
)


def extra_fields(record: logging.LogRecord) -> dict:
    """Return the fields attached through `extra=`, request_id excluded (it gets its own slot)."""
    return {key: value for key, value in vars(record).items() if key not in STANDARD_ATTRS and key != "request_id"}


class JsonFormatter(logging.Formatter):
    """Render each record as one JSON line: ts, level, logger, func, msg, request_id, extras, exc."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize the record; values json cannot encode fall back to str()."""
        payload = {
            "ts": datetime.fromtimestamp(record.created).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "func": record.funcName,
            "msg": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id is not None:
            payload["request_id"] = request_id
        payload.update(extra_fields(record))
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def main():
    pass


if __name__ == "__main__":
    main()
