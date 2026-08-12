from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sentry_sdk

from app.core.config import settings
from app.core.db import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 AutoAI Platform startuje...")
    Base.metadata.create_all(bind=engine)
    print("✅ Baza podataka inicijalizovana")

    # Migracije — dodaj kolone ako ne postoje
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE listings
                ADD COLUMN IF NOT EXISTS contact_type VARCHAR(20) DEFAULT 'unknown',
                ADD COLUMN IF NOT EXISTS contact_url TEXT
        """))
        conn.commit()
    print("✅ Migracija contact_type/contact_url primenjena")
    print("🛑 AutoAI external data updates are disabled")

    yield

    print("👋 AutoAI Platform se gasi")


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "environment": settings.APP_ENV,
        "external_data_updates": "disabled",
    }


from app.api import search, listings, users, alerts, ai_chat, analyze, admin, vin, inbox

app.include_router(search.router,    prefix="/api/v1/search",   tags=["🔍 Pretraga"])
app.include_router(listings.router,  prefix="/api/v1/listings", tags=["🚗 Oglasi"])
app.include_router(users.router,     prefix="/api/v1/users",    tags=["👤 Korisnici"])
app.include_router(alerts.router,    prefix="/api/v1/alerts",   tags=["🔔 Alertovi"])
app.include_router(ai_chat.router,   prefix="/api/v1/ai",       tags=["🤖 AI"])
app.include_router(analyze.router,   prefix="/api/v1/analyze",  tags=["🔍 Analiza oglasa"])
app.include_router(admin.router,     prefix="/api/v1/admin",    tags=["⚙️ Admin"])
app.include_router(vin.router,       prefix="/api/v1/vin",      tags=["🔐 VIN"])
app.include_router(inbox.router,     prefix="/api/v1/inbox",    tags=["📬 Inbox"])
