from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Enterprise CRM API"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    MAGIC_LINK_EXPIRE_MINUTES: int = 15
    AUTH_COOKIE_NAME: str = "token"

    # Database
    POSTGRES_SERVER: str | None = None
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_DB: str | None = None
    POSTGRES_PORT: str | None = None
    DATABASE_URL: str

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def sanitize_database_url(cls, v: str) -> str:
        if v and isinstance(v, str):
            v = v.strip().strip('"').strip("'")
            while v.startswith("DATABASE_URL="):
                v = v[len("DATABASE_URL=") :].strip()
        return v

    # Redis & Celery
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # AWS S3 / MinIO Storage
    AWS_ENDPOINT_URL: str = "http://minio:9000"
    AWS_ACCESS_KEY_ID: str = "minioadmin"
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_S3_BUCKET: str = "crm-enterprise-bucket"
    AWS_REGION: str = "us-east-1"

    # Document upload hardening
    MAX_DOCUMENT_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MiB
    DOCUMENT_UPLOAD_BUFFER_BYTES: int = 1024 * 1024  # 1 MiB streaming chunk

    # SMTP Gmail Email Configuration
    SMTP_HOST: str | None = "smtp-relay.brevo.com"
    SMTP_PORT: int | None = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: str = "selvakumar.dev3@gmail.com"
    EMAILS_FROM_PASSWORD: str | None = None
    EMAILS_FROM_NAME: str = "Enterprise CRM Support"
    RESET_TOKEN_EXPIRE_MINUTES: int = 60
    BREVO_API_KEY: str | None = None
    # Resend Email API (primary — HTTPS based email delivery)
    RESEND_API_KEY: str | None = None

    # Stripe Configuration
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_PUBLISHABLE_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None

    # AI API Keys
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    ENVIRONMENT: str = "development"
    # CORS & Frontend URLs
    CORS_ORIGINS: str = (
        "https://crm-one-sable.vercel.app,http://localhost:3000,http://127.0.0.1:3000"
    )
    FRONTEND_URL: str = "https://crm-one-sable.vercel.app,http://localhost:3000"

    @property
    def frontend_base_url(self) -> str:
        if self.FRONTEND_URL:
            urls = [u.strip() for u in self.FRONTEND_URL.split(",") if u.strip()]
            if urls:
                return urls[0].rstrip("/")
        return "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def auth_cookie_secure(self) -> bool:
        return self.ENVIRONMENT.lower() not in {"development", "test"}

    @property
    def auth_cookie_samesite(self) -> Literal["lax", "none"]:
        # The deployed frontend and API use different sites, which requires
        # SameSite=None. Local HTTP development uses Lax because Secure cookies
        # are intentionally unavailable there.
        return "none" if self.auth_cookie_secure else "lax"

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")


settings = Settings()
