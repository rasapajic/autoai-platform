# 🚗 AutoAI Platform

AI platforma za pretragu polovnih automobila u Evropi.

## Brzi Start

```bash
# 1. Kloniraj projekat
git clone https://github.com/tvojacc/autoai-platform
cd autoai-platform

# 2. Pokretanje (sve u jednoj komandi)
chmod +x scripts/start.sh
./scripts/start.sh
```

Platforma je dostupna na: **http://localhost:3000**

---

## M0.2 Internal Scheduled Listings Refresh

The guarded internal pipeline covers the five sources that populated the legacy
production catalog: Willhaben, AutoScout24, Marktplaats, 2dehands, and
Kleinanzeigen. Public/commercial external listing use remains disabled.

The Railway cron service `appealing-communication` runs at 02:00 and 14:00 UTC.
It calls the secret-protected `POST /api/v1/internal/m01/scheduled-refresh`
endpoint with at most three pages per source.

Each cycle stages a valid, non-empty batch from every source before opening a
database transaction. Existing listings are updated in place, new listings are
inserted, and missing historical-source listings are marked inactive. Records
are not deleted, so favorites, price history, and conversations remain linked.
A source or database failure leaves the existing catalog unchanged.

Required backend variables:

```text
AUTOAI_ADMIN_SECRET=<new random secret>
AUTOAI_INTERNAL_LISTING_INGEST_ENABLED=true
AUTOAI_INTERNAL_LISTING_SOURCES=willhaben,autoscout24,marktplaats,2dehands,kleinanzeigen
```

Required cron variables:

```text
AUTOAI_ADMIN_SECRET=<same backend secret>
AUTOAI_BACKEND_URL=https://autoai-platform-production.up.railway.app
AUTOAI_CRON_MAX_PAGES=3
```

`POST /api/v1/internal/m01/probe-all` remains available for read-only source
validation. The destructive M0.1 recovery endpoint is retained only for
emergency, explicitly confirmed recovery and is not used by the cron service.

---

## Struktura Projekta

```
autoai-platform/
├── backend/               # Python FastAPI backend
│   ├── app/
│   │   ├── api/           # API endpointi
│   │   ├── scrapers/      # Web scraperi
│   │   ├── models/        # SQLAlchemy modeli
│   │   ├── ai/            # AI komponente
│   │   └── core/          # Config, DB, Auth
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/              # Next.js frontend
├── ml/                    # ML modeli
├── nginx/                 # Nginx konfiguracija
├── scripts/
│   ├── init.sql           # Inicijalizacija baze
│   └── start.sh           # Startup skripta
├── docker-compose.yml
└── .env.example
```

## Servisi

| Servis        | Port  | Opis                          |
|---------------|-------|-------------------------------|
| Frontend      | 3000  | Next.js web aplikacija        |
| Backend API   | 8000  | FastAPI REST API              |
| API Docs      | 8000/docs | Swagger dokumentacija     |
| PostgreSQL    | 5432  | Glavna baza podataka          |
| Redis         | 6379  | Cache i task queue            |
| Elasticsearch | 9200  | Full-text pretraga            |

## Faze Razvoja

- [x] **Faza 01** — Infrastruktura & Baza
- [ ] **Faza 02** — Web Scraper Engine
- [ ] **Faza 03** — Backend API
- [ ] **Faza 04** — AI Komponente
- [ ] **Faza 05** — Frontend
- [ ] **Faza 06** — Deployment & Launch

## Korisni Komandi

```bash
# Logovi svih servisa
docker compose logs -f

# Logovi samo backend-a
docker compose logs -f backend

# Resetuj bazu
docker compose down -v && docker compose up -d

# Pristupi PostgreSQL konzoli
docker compose exec postgres psql -U admin -d autoai

# Pristupi Redis konzoli
docker compose exec redis redis-cli
```
