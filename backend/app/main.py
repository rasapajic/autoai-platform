from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
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

    if settings.AUTOAI_INTERNAL_LISTING_INGEST_ENABLED:
        print("🧪 AutoAI M0.2 internal scheduled listing refresh is ENABLED")
    else:
        print("🛑 AutoAI external listing ingest is disabled by default")

    yield

    print("👋 AutoAI Platform se gasi")


if settings.APP_ENV == "production" and settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,
        environment=settings.APP_ENV,
    )

app = FastAPI(
    title="AutoAI Platform API",
    description="AI platforma za pretragu polovnih automobila u Evropi",
    version="1.0.3-m02-scheduled-refresh",
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


@app.middleware("http")
async def require_internal_access(request: Request, call_next):
    """Protect all public AutoAI API routes while the product is internal-only."""
    if not settings.INTERNAL_ACCESS_REQUIRED:
        return await call_next(request)

    path = request.url.path
    if (
        request.method == "OPTIONS"
        or path == "/health"
        or path == "/api/v1/users/login"
        or path.startswith("/api/v1/internal/m01")
        or not path.startswith("/api/v1/")
    ):
        return await call_next(request)

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "AutoAI je trenutno dostupan samo ovlašćenim korisnicima."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if not payload.get("sub"):
            raise JWTError("missing subject")
    except JWTError:
        return JSONResponse(
            status_code=401,
            content={"detail": "Prijava je istekla ili nije važeća."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await call_next(request)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.3-m02-scheduled-refresh",
        "environment": settings.APP_ENV,
        "external_data_updates": (
            "internal_scheduled_refresh"
            if settings.AUTOAI_INTERNAL_LISTING_INGEST_ENABLED
            else "disabled"
        ),
    }


from app.api import search, listings, users, alerts, ai_chat, analyze, vin, inbox, m01_listings

app.include_router(search.router,    prefix="/api/v1/search",   tags=["🔍 Pretraga"])
app.include_router(listings.router,  prefix="/api/v1/listings", tags=["🚗 Oglasi"])
app.include_router(users.router,     prefix="/api/v1/users",    tags=["👤 Korisnici"])
app.include_router(alerts.router,    prefix="/api/v1/alerts",   tags=["🔔 Alertovi"])
app.include_router(ai_chat.router,   prefix="/api/v1/ai",       tags=["🤖 AI"])
app.include_router(analyze.router,   prefix="/api/v1/analyze",  tags=["🔍 Analiza oglasa"])
# Legacy /api/v1/admin router is intentionally not mounted because its secret
# was committed in plaintext. Internal refresh uses environment-backed auth.
app.include_router(
    m01_listings.router,
    prefix="/api/v1/internal/m01",
    tags=["🧪 M0.2 Internal Listings Refresh"],
)
app.include_router(vin.router,       prefix="/api/v1/vin",      tags=["🔐 VIN"])
app.include_router(inbox.router,     prefix="/api/v1/inbox",    tags=["📬 Inbox"])
