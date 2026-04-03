import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.middleware.logging import configure_logging, logging_middleware
from app.proxy.client import ProxyClient
from app.routes.health import router as health_router
from app.routes.proxy import router as proxy_router

logger = logging.getLogger("gateway")


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "method": request.method,
            "path": request.url.path,
        },
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    app.state.proxy_client = ProxyClient(settings)
    yield
    await app.state.proxy_client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="ms-gateway", lifespan=lifespan)

    # Rate limiting
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[settings.rate_limit_default],
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request/response logging + request ID injection
    app.middleware("http")(logging_middleware)

    # Routes — health before proxy so it is never caught by the catch-all
    app.include_router(health_router)
    app.include_router(proxy_router)

    return app


app = create_app()
