from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.v1.api import api_router
from app.database import engine
from app.models import Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto create all 70 database tables on startup
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"Database initialization info: {e}")
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description="Enterprise CRM Backend API with FastAPI, PostgreSQL, Redis, Celery, and AI Integration",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware for Next.js Frontend
# Allowed origins are read from the CORS_ORIGINS env var (comma-separated).
# Additionally, any *.vercel.app preview/production deployment URL matching
# our project pattern is allowed via regex, so new Vercel deployments don't
# require a code change.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"https://crm.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "message": "Enterprise CRM Backend API is running",
        "docs": "/docs",
        "health": "OK",
        "tables_count": 70
    }