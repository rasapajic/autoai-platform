from pydantic_settings import BaseSettings
from functools import lru_cache
import json


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "promeniti-u-produkciji"
    CORS_ORIGINS: str = '["http://localhost:3000"]'

    # AutoAI M0.1 Live Listings Recovery
    AUTOAI_ADMIN_SECRET: str = ""
    AUTOAI_INTERNAL_LISTING_INGEST_ENABLED: bool = False
    AUTOAI_INTERNAL_LISTING_SOURCES: str = (
        "willhaben,autoscout24,marktplaats,2dehands,kleinanzeigen"
    )

    # Database
    DATABASE_URL: str = "postgresql://admin:secret123@localhost:5432/autoai"
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    # Elasticsearch
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    # AI
    ANTHROPIC_API_KEY: str = ""
    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 7 dana
    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    def get_cors_origins(self) -> list[str]:
        try:
            return json.loads(self.CORS_ORIGINS)
        except Exception:
            return [self.CORS_ORIGINS]

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
