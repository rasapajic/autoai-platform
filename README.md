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

## M0.4 Resumable Internal Catalog

The guarded internal pipeline covers Willhaben, AutoScout24, Marktplaats,
2dehands and Kleinanzeigen. Public/commercial ingestion remains disabled.
The approved compact interface is unchanged.

The Railway cron service `appealing-communication` runs at 02:00, 08:00, 14:00
and 20:00 UTC. With `AUTOAI_CATALOG_CURSORS_ENABLED=true`, it calls the secret-protected
`POST /api/v1/internal/m01/collect-window` for each of 16 fixed partitions,
with at most three pages per partition. The 02:00 UTC run refreshes the first
pages; the other three runs advance durable page cursors. Rows and their cursor
commit together. A failed partition keeps its checkpoint while other partitions
continue. The cron explicitly reports partial failures and fails if an entire
source has no valid observations.

Vehicle names are normalized from readable source labels, titles or URL slugs.
Unknown taxonomy codes remain unknown; numeric models such as 208, 500 and 911
are preserved. Existing listings update in place and unseen rows remain stored;
absence from a search sample does not prove removal. Identity or price changes
clear stale valuation fields. Automated AI valuation remains disabled.

Growth pauses above 250 MiB of database size. This does not replace monitoring
of the 500 MB volume and PostgreSQL WAL. Accepted rows, unresolved makes,
active totals and next-page checkpoints are logged. Without the feature flag,
the existing all-source bounded scheduled refresh remains the fallback.

The target is 10,000 → 50,000 → 200,000+ current listings. Resumable collection
is the current milestone; full source coverage, freshness checks, physical
vehicle deduplication and sufficiently populated comparison cohorts remain.
See [catalog scaling](docs/CATALOG-SCALING.md).

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
AUTOAI_CATALOG_CURSORS_ENABLED=true
AUTOAI_CATALOG_SCAN_MODE=auto
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
