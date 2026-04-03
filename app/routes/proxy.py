import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.auth.jwt import get_current_claims
from app.config import Settings, get_settings
from app.proxy.client import HOP_BY_HOP, ProxyClient

logger = logging.getLogger("gateway")

router = APIRouter()


def _get_proxy_client(request: Request) -> ProxyClient:
    return request.app.state.proxy_client


def _resolve_upstream(path: str, settings: Settings) -> str:
    """Match the longest configured prefix to find the upstream base URL."""
    normalized = path if path.startswith("/") else f"/{path}"
    match = None
    for prefix, base_url in settings.services.items():
        p = prefix if prefix.startswith("/") else f"/{prefix}"
        if normalized.startswith(p) and (match is None or len(p) > len(match[0])):
            match = (p, base_url)

    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No service configured for path: {normalized}",
        )

    prefix, base_url = match
    remainder = normalized[len(prefix):]
    return f"{base_url.rstrip('/')}/{remainder.lstrip('/')}"


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy(
    path: str,
    request: Request,
    claims: Annotated[dict, Depends(get_current_claims)],
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[ProxyClient, Depends(_get_proxy_client)],
) -> Response:
    upstream_url = _resolve_upstream(f"/{path}", settings)

    forward_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP
    }
    # Propagate verified identity to downstream services
    forward_headers["X-User-ID"] = str(claims.get("sub", ""))
    forward_headers["X-Request-ID"] = getattr(request.state, "request_id", "")

    body = await request.body()

    try:
        upstream = await client.forward(
            method=request.method,
            url=upstream_url,
            headers=forward_headers,
            content=body,
            params=dict(request.query_params),
        )
    except httpx.TimeoutException as exc:
        logger.error("upstream_timeout", extra={"url": upstream_url})
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Upstream service timed out",
        ) from exc
    except Exception as exc:
        logger.error("upstream_error", extra={"url": upstream_url, "error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream service unavailable",
        ) from exc

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={k: v for k, v in upstream.headers.items() if k.lower() not in HOP_BY_HOP},
        media_type=upstream.headers.get("content-type"),
    )
