from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "promeniti-u-produkciji"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

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

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
