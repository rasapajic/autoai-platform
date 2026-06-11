FROM python:3.11-slim

WORKDIR /app

COPY . /app/

RUN pip install --no-cache-dir psycopg2-binary aiohttp anthropic

RUN ls -la /app/

CMD ["python", "/app/scraper.py"]
