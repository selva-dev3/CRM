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
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/crm_db"

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
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = "selvakumar.dev3@gmail.com"
    SMTP_PASSWORD: Optional[str] = "cxwromupefrpeovz"
    EMAILS_FROM_EMAIL: str = "selvakumar.dev3@gmail.com"
    EMAILS_FROM_NAME: str = "Enterprise CRM Support"
    RESET_TOKEN_EXPIRE_MINUTES: int = 60

    # AI API Keys
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        extra="ignore"
    )

settings = Settings()
