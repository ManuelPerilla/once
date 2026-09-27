import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from src import database
from src.accounts.models import AdminAccount
from src.accounts.permissions import permissions_for, required_permission
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
            status.HTTP_401_UNAUTHORIZED, "No autenticado. Falta la cookie o el token de sesión."
        )
    try:
        settings = get_auth_settings()
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[ALGORITHM], options={"require": ["sub", "exp"]}
        )
        username = payload["sub"]
        role = "admin"
        if username != settings.admin_username:
            with Session(database.engine) as auth_session:
                account = auth_session.exec(
                    select(AdminAccount).where(AdminAccount.username == username)
                ).first()
                if (
                    not account
                    or not account.active
                    or payload.get("auth_version") != account.token_version
                ):
                    raise jwt.InvalidTokenError("Cuenta no autorizada o sesión revocada")
                role = account.role
        permissions = permissions_for(role)
        # route.path is stable even when the reverse proxy supplies a root_path.
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        if required_permission(request.method, path) not in permissions:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Tu cuenta no tiene permiso para esta acción."
            )
        request.state.actor, request.state.role = username, role
        request.state.permissions = permissions
        return username
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Token expirado. Por favor, inicia sesión de nuevo."
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido.") from exc


def get_session(request: Request):
    """One transaction scope per request, with the authenticated actor attached."""
    with Session(database.engine) as session:
        session.info["request"] = request
        session.info["actor"] = getattr(request.state, "actor", None)
        yield session
