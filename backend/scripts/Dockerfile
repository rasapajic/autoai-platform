FROM python:3.11-slim

WORKDIR /app

# Instaliraj dependencies
RUN pip install --no-cache-dir psycopg2-binary aiohttp anthropic

# scraper.py će biti na /app/scripts/scraper.py
# app/ modul mora biti dostupan
# Ovo se rešava kroz sys.path u scraper.py

CMD ["python", "scraper.py"]
