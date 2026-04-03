from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import Settings, get_settings

_bearer = HTTPBearer()


def decode_token(token: str, settings: Settings) -> dict:
    try:
        kwargs: dict = {"algorithms": [settings.jwt_algorithm]}
        if settings.jwt_audience:
            kwargs["audience"] = settings.jwt_audience
        if settings.jwt_issuer:
            kwargs["issuer"] = settings.jwt_issuer
        return jwt.decode(token, settings.jwt_secret, **kwargs)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_claims(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return decode_token(credentials.credentials, settings)
