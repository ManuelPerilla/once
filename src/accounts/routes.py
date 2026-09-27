"""Administrator-managed accounts; password hashes never leave this module."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from src.accounts.models import AdminAccount
from src.accounts.permissions import permissions_for
from src.api.dependencies import get_session, verificar_token
from src.audit.service import record_change
from src.models import utcnow
from src.security import get_auth_settings, hash_password

router = APIRouter(prefix="/accounts", dependencies=[Depends(verificar_token)])
Role = Literal["auditor", "editor", "operator", "admin"]


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=100)
    role: Role = "auditor"
    password: str = Field(min_length=12, max_length=1024, repr=False)

    @field_validator("username")
    @classmethod
    def normalize(cls, value):
        return value.casefold()

    @field_validator("display_name")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Escribe el nombre de la persona")
        return value.strip()


class AccountPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: Role | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=1024, repr=False)
    reason: str = Field(min_length=3, max_length=1000)


def public_account(row):
    return {
        "id": row.id,
        "username": row.username,
        "display_name": row.display_name,
        "role": row.role,
        "permissions": permissions_for(row.role),
        "active": row.active,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.get("")
def list_accounts(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_session),
):
    total = session.exec(select(func.count()).select_from(AdminAccount)).one()
    rows = session.exec(
        select(AdminAccount)
        .order_by(AdminAccount.username)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [public_account(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "bootstrap_username": get_auth_settings().admin_username,
    }


@router.post("", status_code=201)
def create_account(
    data: AccountCreate,
    session: Session = Depends(get_session),
    actor: str = Depends(verificar_token),
):
    if data.username == get_auth_settings().admin_username.casefold():
        raise HTTPException(409, "Ese nombre está reservado para el administrador de recuperación")
    if session.exec(select(AdminAccount).where(AdminAccount.username == data.username)).first():
        raise HTTPException(409, "Ya existe una cuenta con ese nombre")
    if session.exec(select(func.count()).select_from(AdminAccount)).one() >= 100:
        raise HTTPException(409, "El piloto admite hasta 100 cuentas identificadas")
    row = AdminAccount(
        username=data.username,
        display_name=data.display_name,
        role=data.role,
        password_hash=hash_password(data.password),
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "Ya existe una cuenta con ese nombre") from exc
    record_change(
        session,
        entity_type="account",
        entity_id=row.id,
        field="account",
        before=None,
        after=public_account(row),
        action="account_create",
        actor=actor,
        reason="Alta de una persona autorizada",
        version=row.token_version,
    )
    session.commit()
    session.refresh(row)
    return public_account(row)


@router.patch("/{account_id}")
def update_account(
    account_id: int,
    data: AccountPatch,
    session: Session = Depends(get_session),
    actor: str = Depends(verificar_token),
):
    row = session.exec(
        select(AdminAccount).where(AdminAccount.id == account_id).with_for_update()
    ).first()
    if row is None:
        raise HTTPException(404, "Cuenta no encontrada")
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    changes.pop("reason", None)
    effective = []
    for field, value in changes.items():
        if field == "display_name":
            value = value.strip()
            if not value:
                raise HTTPException(422, "Escribe el nombre de la persona")
        before = "[contraseña protegida]" if field == "password" else getattr(row, field)
        if field != "password" and before == value:
            continue
        effective.append((field, before, "[contraseña renovada]" if field == "password" else value))
        setattr(
            row,
            "password_hash" if field == "password" else field,
            hash_password(value) if field == "password" else value,
        )
    if effective:
        row.token_version += 1
        row.updated_at = utcnow()
        session.add(row)
        for field, before, after in effective:
            record_change(
                session,
                entity_type="account",
                entity_id=row.id,
                field=field,
                before=before,
                after=after,
                action="account_update",
                actor=actor,
                reason=data.reason,
                version=row.token_version,
            )
        session.commit()
        session.refresh(row)
    return public_account(row)
