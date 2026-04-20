from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sentry_sdk

from app.core.config import settings
from app.core.db import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 AutoAI Platform startuje...")
    Base.metadata.create_all(bind=engine)
    print("✅ Baza podataka inicijalizovana")
    yield
    # Shutdown
    print("👋 AutoAI Platform se gasi")


# Sentry monitoring (samo u produkciji)
if settings.APP_ENV == "production":
    sentry_sdk.init(
        dsn="tvoj_sentry_dsn_ovde",
        traces_sample_rate=0.1,
        environment=settings.APP_ENV,
    )

app = FastAPI(
    title="AutoAI Platform API",
    description="AI platforma za pretragu polovnih automobila u Evropi",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health check ─────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "environment": settings.APP_ENV,
    }


from app.api import search, listings, users, alerts, ai_chat

app.include_router(search.router,   prefix="/api/v1/search",   tags=["🔍 Pretraga"])
app.include_router(listings.router, prefix="/api/v1/listings", tags=["🚗 Oglasi"])
app.include_router(users.router,    prefix="/api/v1/users",    tags=["👤 Korisnici"])
app.include_router(alerts.router,   prefix="/api/v1/alerts",   tags=["🔔 Alertovi"])
app.include_router(ai_chat.router,  prefix="/api/v1/ai",       tags=["🤖 AI"])
