from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.api.dependencies import get_session, verificar_token
from src.providers import ProviderError

from .collections import COLLECTIONS
from .schemas import ApplyCatalog
from .service import CatalogError, apply, prepare

router = APIRouter(
    prefix="/catalog", tags=["Catálogo abierto"], dependencies=[Depends(verificar_token)]
)


@router.get("/collections")
def collections():
    return [
        {
            "id": key,
            "name": value["name"],
            "description": value["description"],
            "count": len(value["entries"]),
            "provider": "wikidata",
            "license": "CC0-1.0",
        }
        for key, value in COLLECTIONS.items()
    ]


@router.post("/prepare/{collection}")
def prepare_collection(collection: str, session: Session = Depends(get_session)):
    try:
        return prepare(session, collection, interactive=True)
    except CatalogError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/batches/{batch_id}/apply")
def apply_batch(batch_id: str, request: ApplyCatalog, session: Session = Depends(get_session)):
    try:
        return apply(session, batch_id, request.decisions)
    except CatalogError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Otro cambio entró en conflicto. Revisa la vista previa; no se aplicó el lote.",
        ) from exc
