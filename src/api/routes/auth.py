import datetime
import hmac

import jwt
from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel
from sqlmodel import Field

from src.api.dependencies import ALGORITHM
from src.security import get_auth_settings, verify_password

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)


@router.post("/login")
def login(credentials: LoginRequest, response: Response):
    settings = get_auth_settings()
    password_ok = verify_password(credentials.password, settings.admin_password_hash)
    username_ok = hmac.compare_digest(
        credentials.username.encode("utf-8"), settings.admin_username.encode("utf-8")
    )
    if username_ok and password_ok:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
        payload = {"sub": credentials.username, "exp": expire}
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
        return {"ok": True, "mensaje": "Sesión iniciada correctamente"}
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
