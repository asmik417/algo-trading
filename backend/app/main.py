"""FastAPI app factory: CORS, the v1 routers, error mapping, DB init + seed, and the daily scheduler on startup.
Run with `uvicorn app.main:app --port 8000`; interactive docs at /docs.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal, init_db
from app.jobs import scheduler
from app.services import backtest_service, market_data, profile_service, suggestion_service
from app.services.errors import ServiceError

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with SessionLocal() as db:
        profile_service.seed_default_profile(db)
        suggestion_service.recover_interrupted_runs(db)
        backtest_service.recover_interrupted(db)
    log.info("Database ready at %s", settings.DATABASE_URL.split("///")[-1])
    if settings.WARM_PANEL:
        market_data.warm_up()
    if settings.ENABLE_SCHEDULER:
        scheduler.start()
    yield
    scheduler.shutdown()


def _validation_message(exc: RequestValidationError) -> str:
    """Pydantic's error list -> one readable sentence, per the contract's {"detail": "message"}."""
    parts = []
    for err in exc.errors():
        where = ".".join(str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path"))
        parts.append(f"{where}: {err.get('msg')}" if where else str(err.get("msg")))
    return "; ".join(parts) or "Invalid request."


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Trade Assistant API",
        version="1.0.0",
        description="Paper-trading strategy lab: suggest, plan, track and grade NSE stock picks.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ServiceError)
    async def _service_error(_req: Request, exc: ServiceError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, **exc.extra})

    @app.exception_handler(RequestValidationError)
    async def _bad_request(_req: Request, exc: RequestValidationError):
        return JSONResponse(status_code=400, content={"detail": _validation_message(exc)})

    app.include_router(api_router, prefix=settings.API_PREFIX)
    return app


app = create_app()
