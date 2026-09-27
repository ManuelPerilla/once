from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from src.api.dependencies import get_session, verificar_token

from . import queries
from .schemas import ControlPage, ControlSummary, EntityKind, RecordKind

router = APIRouter(
    prefix="/control", tags=["Control de datos"], dependencies=[Depends(verificar_token)]
)


@router.get("/summary", response_model=ControlSummary)
def control_summary(session: Session = Depends(get_session)):
    return queries.summary(session)


@router.get("/records", response_model=ControlPage)
def control_records(
    kind: RecordKind,
    provider: str | None = Query(default=None, max_length=100),
    entity_type: EntityKind | None = None,
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    if kind == "imports" and entity_type:
        raise HTTPException(
            status_code=422, detail="Los lotes se filtran por colección, no por registro."
        )
    return queries.records(session, kind, provider, entity_type, search, page, page_size)


@router.get("/issues", response_model=ControlPage)
def control_issues(
    code: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    if code not in {check.code for check in queries.CHECKS}:
        raise HTTPException(status_code=422, detail="Revisión desconocida.")
    return queries.issues(session, code, page, page_size)
