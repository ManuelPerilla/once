"""ASGI composition root. Business rules and handlers belong to their modules."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import Session

from src import database
from src.api.routes import auth, context, entities, matches, providers, public
from src.catalog.routes import router as catalog_router
from src.football.rules import FootballRuleError
from src.security import get_auth_settings
from src.seed import ejecutar_seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_auth_settings()
    database.crear_tablas_db()
    with Session(database.engine) as session:
        ejecutar_seed(session)
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="ONCE API", lifespan=lifespan, root_path=os.getenv("ROOT_PATH", ""))
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

    for router in (
        catalog_router,
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
