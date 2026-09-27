import datetime
import hmac

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlmodel import Field, Session, select

from src.accounts.models import AdminAccount
from src.accounts.permissions import permissions_for
from src.api.dependencies import ALGORITHM, get_session
from src.security import get_auth_settings, verify_password

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)


@router.post("/login")
def login(credentials: LoginRequest, response: Response, session: Session = Depends(get_session)):
    settings = get_auth_settings()
    bootstrap = hmac.compare_digest(
        credentials.username.encode("utf-8"), settings.admin_username.encode("utf-8")
    )
    account = (
        None
        if bootstrap
        else session.exec(
            select(AdminAccount).where(
                AdminAccount.username == credentials.username.strip().casefold()
            )
        ).first()
    )
    expected = account.password_hash if account else settings.admin_password_hash
    password_ok = verify_password(credentials.password, expected)
    if password_ok and (bootstrap or (account and account.active)):
        username = settings.admin_username if bootstrap else account.username
        role = "admin" if bootstrap else account.role
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
        payload = {
            "sub": username,
            "exp": expire,
            "auth_version": account.token_version if account else 0,
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
        response.set_cookie(
            key="vertice_token",
            value=token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            max_age=86400,
            path="/",
        )
        return {
            "ok": True,
            "mensaje": "Sesión iniciada correctamente",
            "username": username,
            "role": role,
            "permissions": permissions_for(role),
        }
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key="vertice_token",
        path="/",
        httponly=True,
        secure=get_auth_settings().cookie_secure,
        samesite="lax",
    )
    return {"ok": True, "mensaje": "Sesión cerrada"}
