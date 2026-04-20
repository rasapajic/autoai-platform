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
