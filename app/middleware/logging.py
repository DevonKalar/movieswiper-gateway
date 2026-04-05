import json
import logging
import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge any fields passed via extra={}
        skip = logging.LogRecord.__init__.__code__.co_varnames
        for key, val in vars(record).items():
            if key not in skip and not key.startswith("_") and key not in data:
                data[key] = val
        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(data)


def configure_logging() -> None:
    formatter = _JsonFormatter()
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    for name in ("gateway", "uvicorn", "uvicorn.access", "uvicorn.error"):
        log = logging.getLogger(name)
        log.handlers = [handler]
        log.propagate = False
        log.setLevel(logging.INFO)

    # Silence noisy uvicorn access log in favour of our middleware
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


logger = logging.getLogger("gateway")


_SLOW_REQUEST_MS = 150


async def logging_middleware(request: Request, call_next: Callable) -> Response:
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    status_code = response.status_code
    if status_code >= 500:
        logger.warning(
            "response_5xx",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )
    elif duration_ms >= _SLOW_REQUEST_MS:
        logger.warning(
            "slow_request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )

    response.headers["X-Request-ID"] = request_id
    return response
