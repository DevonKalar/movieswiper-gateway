import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("gateway")

from app.config import Settings

# Hop-by-hop headers must not be forwarded to upstream services
HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
    }
)

# Headers set by this gateway from verified state; strip any client-supplied values
# to prevent spoofing (e.g. a client injecting X-User-ID to impersonate another user)
GATEWAY_CONTROLLED_HEADERS = frozenset({"x-user-id"})

_RETRYABLE = (httpx.TimeoutException,)


class ProxyClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.downstream_timeout_seconds),
            follow_redirects=False,
        )

    async def forward(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        content: bytes,
        params: dict[str, str],
    ) -> httpx.Response:
        def _before_sleep(retry_state) -> None:
            logger.warning(
                "upstream_retry",
                extra={
                    "url": url,
                    "attempt": retry_state.attempt_number,
                    "error": str(retry_state.outcome.exception()),
                },
            )

        @retry(
            retry=retry_if_exception_type(_RETRYABLE),
            stop=stop_after_attempt(self._settings.downstream_max_retries),
            wait=wait_exponential(
                multiplier=self._settings.downstream_retry_backoff,
                min=0.1,
                max=5.0,
            ),
            before_sleep=_before_sleep,
            reraise=True,
        )
        async def _send() -> httpx.Response:
            return await self._client.request(
                method,
                url,
                headers=headers,
                content=content,
                params=params,
            )

        return await _send()

    async def aclose(self) -> None:
        await self._client.aclose()
