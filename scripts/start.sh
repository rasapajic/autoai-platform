#!/bin/bash
# ============================================================
# AutoAI Platform - Startup Script
# Pokreni: chmod +x scripts/start.sh && ./scripts/start.sh
# ============================================================

set -e

echo "╔═══════════════════════════════════╗"
echo "║      AutoAI Platform Setup        ║"
echo "╚═══════════════════════════════════╝"

# 1. Kopiraj .env ako ne postoji
if [ ! -f .env ]; then
    echo "📋 Kreiram .env fajl..."
    cp .env.example .env
    echo "⚠️  Otvori .env i popuni ANTHROPIC_API_KEY!"
fi

# 2. Pokreni servise
echo ""
echo "🐳 Pokrećem Docker servise..."
docker compose up -d postgres redis

# 3. Sačekaj da baza bude spremna
echo "⏳ Čekam da PostgreSQL bude spreman..."
sleep 5
until docker compose exec postgres pg_isready -U admin -d autoai; do
    echo "   Čekam..."
    sleep 2
done

# 4. Pokreni sve servise
echo ""
echo "🚀 Pokrećem sve servise..."
docker compose up -d

echo ""
echo "✅ Platforma pokrenuta!"
echo ""
echo "📍 Dostupno na:"
echo "   Frontend:  http://localhost:3000"
echo "   Backend:   http://localhost:8000"
echo "   API Docs:  http://localhost:8000/docs"
echo ""
echo "📊 Korisni komandi:"
echo "   Logovi:     docker compose logs -f"
echo "   Zaustavi:   docker compose down"
echo "   Resetuj DB: docker compose down -v && docker compose up -d"
