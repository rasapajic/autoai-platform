import json

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "promeniti-u-produkciji"
    CORS_ORIGINS: str = "http://localhost:3000"

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
    SMTP_FROM: str = ""

    # URLs
    NEXT_PUBLIC_APP_URL: str = ""
    FRONTEND_URL: str = ""

    # Scraping
    ENABLE_SCHEDULED_SCRAPING: bool = False

    @property
    def cors_origins(self) -> list[str]:
        raw = str(self.CORS_ORIGINS or "").strip()
        if not raw:
            return []
        if raw.startswith("["):
            return json.loads(raw)
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def app_base_url(self) -> str:
        return (self.NEXT_PUBLIC_APP_URL or self.FRONTEND_URL or "").strip().rstrip("/")

    def app_url(self, path: str = "") -> str:
        base_url = self.app_base_url
        if not base_url:
            raise ValueError("NEXT_PUBLIC_APP_URL or FRONTEND_URL must be configured for public app links")
        if not path:
            return base_url
        return f"{base_url}/{path.lstrip('/')}"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
