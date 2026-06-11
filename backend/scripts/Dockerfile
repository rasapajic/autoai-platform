FROM python:3.11-slim

WORKDIR /app

# Kopiraj ceo backend (potreban je za imports)
COPY .. .

# Instaliraj samo što treba
RUN pip install --no-cache-dir psycopg2-binary aiohttp anthropic

CMD ["python", "scripts/scraper.py"]
