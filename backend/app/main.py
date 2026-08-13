from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db.session import AsyncSessionLocal, engine
from app.models import Base

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup / shutdown.
    Only create tables automatically in development.
    Production should use Alembic migrations.
    """
    environment = settings.ENVIRONMENT.lower()

    if environment == "development":
        logger.info("Development mode - creating database tables if missing")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:  # pragma: no cover - startup failure path
            logger.error("Database initialization failed: %s", e)
    else:
        logger.info(
            "Production mode - skipping create_all(). Using Alembic migrations."
        )

    yield

    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise CRM Backend API with FastAPI, PostgreSQL, Redis, Celery, and AI Integration",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

register_exception_handlers(app)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(
    api_router,
    prefix=settings.API_V1_STR,
)


@app.get("/")
async def root():
    return {
        "message": "Enterprise CRM Backend API is running",
        "health": "OK",
        "docs": "/docs",
        "version": "1.0.0",
    }


@app.get("/health", tags=["Health"])
async def health():
    """Health check that verifies database connectivity, not just process liveness."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        logger.error("Health check failed: database unreachable: %s", e)
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unreachable"},
        )
    return {"status": "ok", "database": "ok"}
