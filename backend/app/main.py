from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db, init_db
from .schemas import (
    AccusationRequest,
    AccusationReview,
    AccusationReviewRequest,
    AccusationResult,
    GameState,
    HealthResponse,
    InterrogationRequest,
    InterrogationResponse,
    InvestigationRequest,
    InvestigationResponse,
)
from .service import GameService


settings = get_settings()
service = GameService(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    docs_url=f"{settings.api_prefix}/docs",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(f"{settings.api_prefix}/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    db.execute(text("SELECT 1"))
    return HealthResponse(
        status="ok",
        database="connected",
        kimi_configured=service.kimi.available,
        model=settings.kimi_model,
        engine_version="truth-dialogue-v2",
    )


@app.post(f"{settings.api_prefix}/cases", response_model=GameState)
async def create_case(db: Session = Depends(get_db)) -> dict:
    return await service.create_game(db)


@app.get(f"{settings.api_prefix}/cases/{{case_id}}", response_model=GameState)
def get_case(case_id: str, db: Session = Depends(get_db)) -> dict:
    return service.get_game(db, case_id)


@app.post(
    f"{settings.api_prefix}/cases/{{case_id}}/interrogations",
    response_model=InterrogationResponse,
)
async def interrogate(
    case_id: str,
    request: InterrogationRequest,
    db: Session = Depends(get_db),
) -> dict:
    return await service.interrogate(db, case_id, request)


@app.post(
    f"{settings.api_prefix}/cases/{{case_id}}/investigations",
    response_model=InvestigationResponse,
)
def investigate(
    case_id: str,
    request: InvestigationRequest,
    db: Session = Depends(get_db),
) -> dict:
    return service.investigate(db, case_id, request)


@app.post(
    f"{settings.api_prefix}/cases/{{case_id}}/accusations/review",
    response_model=AccusationReview,
)
def review_accusation(
    case_id: str,
    request: AccusationReviewRequest,
    db: Session = Depends(get_db),
) -> dict:
    return service.review(db, case_id, request)


@app.post(
    f"{settings.api_prefix}/cases/{{case_id}}/accusations",
    response_model=AccusationResult,
)
def accuse(
    case_id: str,
    request: AccusationRequest,
    db: Session = Depends(get_db),
) -> dict:
    return service.accuse(db, case_id, request)


@app.post(
    f"{settings.api_prefix}/cases/{{case_id}}/accusations/final",
    response_model=AccusationResult,
)
def final_accusation(
    case_id: str,
    request: AccusationRequest,
    db: Session = Depends(get_db),
) -> dict:
    return service.accuse(db, case_id, request)
