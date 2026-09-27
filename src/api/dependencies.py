import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from src import database
from src.security import get_auth_settings

ALGORITHM = "HS256"
security = HTTPBearer(auto_error=False)


def verificar_token(
    request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = request.cookies.get("vertice_token")
    if not token and credentials:
        token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado. Falta la cookie o el token de sesión.",
        )
    try:
        settings = get_auth_settings()
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
        if payload["sub"] != settings.admin_username:
            raise jwt.InvalidTokenError("Usuario no autorizado")
        return payload["sub"]
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado. Por favor, inicia sesión de nuevo.",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
        ) from exc


def get_session():
    """One transaction scope per request; closing rolls back unfinished work."""
    with Session(database.engine) as session:
        yield session
