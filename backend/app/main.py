from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.config import settings
from app.database import engine
from app.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup / shutdown.
    Only create tables automatically in development.
    Production should use Alembic migrations.
    """

    try:
        environment = getattr(settings, "ENVIRONMENT", "development").lower()

        if environment == "development":
            print("Development mode - Creating database tables...")

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            print("Database tables created successfully.")

        else:
            print("Production mode - Skipping create_all(). Using Alembic migrations.")

    except Exception as e:
        print(f"Database initialization failed: {e}")

    yield

    # Optional cleanup
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise CRM Backend API with FastAPI, PostgreSQL, Redis, Celery, and AI Integration",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
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