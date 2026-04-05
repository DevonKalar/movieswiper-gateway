from typing import Annotated
import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import Settings, get_settings

logger = logging.getLogger("gateway")

# auto_error=False lets us return None instead of raising when no token is
# present, so verify_auth can decide based on whether the path is public.
_bearer = HTTPBearer(auto_error=False)


def decode_token(token: str, settings: Settings, *, path: str = "", request_id: str | None = None) -> dict:
    try:
        kwargs: dict = {"algorithms": [settings.jwt_algorithm]}
        if settings.jwt_audience:
            kwargs["audience"] = settings.jwt_audience
        if settings.jwt_issuer:
            kwargs["issuer"] = settings.jwt_issuer
        claims = jwt.decode(token, settings.jwt_secret, **kwargs)
        if not claims.get("sub"):
            logger.warning(
                "auth_denied_missing_sub",
                extra={"path": path, "request_id": request_id},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing subject claim",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return claims
    except JWTError as exc:
        logger.warning(
            "auth_denied_invalid_token",
            extra={"path": path, "request_id": request_id},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def verify_auth(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict | None:
    """
    Returns decoded JWT claims for protected routes, or None for public routes.
    Public routes are prefix-matched against settings.public_paths.
    Raises 401 if a protected route receives no token or an invalid one.
    """
    if any(request.url.path.startswith(p) for p in settings.public_paths):
        return None
    if credentials is None:
        logger.warning(
            "auth_denied_no_credentials",
            extra={
                "path": request.url.path,
                "request_id": getattr(request.state, "request_id", None),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_token(
        credentials.credentials,
        settings,
        path=request.url.path,
        request_id=getattr(request.state, "request_id", None),
    )
