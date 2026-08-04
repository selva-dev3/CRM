from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Enterprise CRM API"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "secret-key-for-jwt-token-hashing"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8 # 8 days
    
    # Database
    POSTGRES_SERVER: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    POSTGRES_PORT: Optional[str] = None
    DATABASE_URL: Optional[str] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def sanitize_database_url(cls, v: Optional[str]) -> Optional[str]:
        if v and isinstance(v, str):
            v = v.strip().strip('"').strip("'")
            while v.startswith("DATABASE_URL="):
                v = v[len("DATABASE_URL="):].strip()
        return v

    # Redis & Celery
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # AWS S3 / MinIO Storage
    AWS_ENDPOINT_URL: str = "http://minio:9000"
    AWS_ACCESS_KEY_ID: str = "minioadmin"
    AWS_SECRET_ACCESS_KEY: str = "minioadmin"
    AWS_S3_BUCKET: str = "crm-enterprise-bucket"
    AWS_REGION: str = "us-east-1"

    # SMTP Gmail Email Configuration
    SMTP_HOST: Optional[str] = "smtp-relay.brevo.com"
    SMTP_PORT: Optional[int] = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: str = "selvakumar.dev3@gmail.com"
    EMAILS_FROM_PASSWORD: Optional[str] = None
    EMAILS_FROM_NAME: str = "Enterprise CRM Support"
    RESET_TOKEN_EXPIRE_MINUTES: int = 60

    # Resend Email API (primary — HTTPS based email delivery)
    RESEND_API_KEY: Optional[str] = None

    # AI API Keys
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # CORS & Frontend URLs
    CORS_ORIGINS: str = "https://crm-one-sable.vercel.app,http://localhost:3000,http://127.0.0.1:3000"
    FRONTEND_URL: str = "https://crm-one-sable.vercel.app"

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

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        extra="ignore"
    )

settings = Settings()