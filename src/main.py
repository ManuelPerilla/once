"""ASGI composition root. Business rules and handlers belong to their modules."""

import asyncio
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src import database
from src.accounts.routes import router as accounts_router
from src.api.routes import auth, context, entities, matches, providers, public, reading
from src.audit.routes import router as audit_router
from src.catalog.routes import router as catalog_router
from src.control.routes import router as control_router
from src.football.routes import router as football_router
from src.football.rules import FootballRuleError
from src.providers.automation_routes import router as source_router
from src.providers.connection import router as connection_router
from src.providers.media_cache import directory as media_directory
from src.security import get_auth_settings
from src.seed import ejecutar_seed
from src.sync.events import router as changes_router
from src.sync.routes import router as automation_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_auth_settings()
    database.crear_tablas_db()
    with Session(database.engine) as session:
        ejecutar_seed(session)
    try:
        yield
    finally:
        hub = getattr(app.state, "change_hub", None)
        if hub and hub.task:
            task = hub.task
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


def create_app() -> FastAPI:
    application = FastAPI(title="ONCE API", lifespan=lifespan, root_path=os.getenv("ROOT_PATH", ""))
    media_directory().mkdir(parents=True, exist_ok=True)
    application.mount("/assets/crests", StaticFiles(directory=media_directory()), name="crests")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if origin.strip()
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(FootballRuleError)
    async def football_rule_error(request: Request, exc: FootballRuleError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @application.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError):
        return JSONResponse(
            status_code=409,
            content={
                "detail": "La operación entra en conflicto con datos vinculados o una identidad existente. Revisa sus relaciones antes de continuar."
            },
        )

    for router in (
        reading.router,
        audit_router,
        football_router,
        automation_router,
        changes_router,
        source_router,
        connection_router,
        accounts_router,
        catalog_router,
        control_router,
        auth.router,
        public.router,
        context.router,
        providers.router,
        entities.router,
        matches.router,
    ):
        application.include_router(router)
    return application


app = create_app()
