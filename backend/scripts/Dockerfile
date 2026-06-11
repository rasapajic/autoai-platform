FROM python:3.11-slim

WORKDIR /app

# Kopiraj ceo backend folder
COPY . /app/

# Instaliraj dependencies
RUN pip install --no-cache-dir psycopg2-binary aiohttp anthropic

CMD ["python", "/app/scripts/scraper.py"]
