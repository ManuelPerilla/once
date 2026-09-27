"""Source capabilities and saved history, without exposing credentials."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from src.api.dependencies import get_session, verificar_token
from src.models import ProviderSnapshot
from src.providers import APIFootballClient

router = APIRouter()


@router.get("/automation/providers", dependencies=[Depends(verificar_token)])
def providers():
    return {
        "items": [
            {
                "id": "openfootball",
                "name": "OpenFootball · archivo colombiano",
                "configured": True,
                "kinds": ["archive"],
                "requires_key": False,
                "seasons": [2023, 2024, 2025],
                "description": "Archivo abierto CC0. 2025 tiene resultados faltantes; no es una fuente de directo ni de la temporada actual.",
            },
            {
                "id": "wikidata",
                "name": "Wikidata y Wikimedia Commons",
                "configured": True,
                "kinds": ["catalog", "history", "media"],
                "requires_key": False,
                "description": "Identidades, hechos históricos y escudos con procedencia. No ofrece marcadores en directo.",
            },
            {
                "id": "api-football",
                "name": "API-Football",
                "configured": APIFootballClient().configured,
                "kinds": [
                    "discovery",
                    "fixtures",
                    "detail",
                    "details_batch",
                    "standings",
                    "standings_batch",
                ],
                "requires_key": True,
                "description": "Calendarios, resultados y detalles según tu cuenta. Comprueba la conexión y elige las temporadas desde Automatización.",
                "free_daily_limit": 100,
            },
        ]
    }


@router.get("/public/history/{entity_type}/{entity_id}")
def history(entity_type: str, entity_id: int, session: Session = Depends(get_session)):
    if entity_type not in {"team", "competition", "confederation"}:
        raise HTTPException(404, "Ficha no disponible")
    row = session.exec(
        select(ProviderSnapshot).where(
            ProviderSnapshot.provider == "wikidata",
            ProviderSnapshot.entity_type == entity_type,
            ProviderSnapshot.local_id == entity_id,
            ProviderSnapshot.kind == "history",
        )
    ).first()
    return {
        **(row.payload if row else {"facts": []}),
        "updated_at": row.fetched_at if row else None,
    }
