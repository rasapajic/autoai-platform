FROM python:3.11-slim

WORKDIR /app

COPY . /app/

RUN pip install --no-cache-dir psycopg2-binary aiohttp anthropic

RUN find /app -type f -name "*.py" | head -20

CMD ["python", "/app/scraper.py"]
