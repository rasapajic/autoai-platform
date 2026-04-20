FROM python:3.11-slim

WORKDIR /app

# Sistemske zavisnosti
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python zavisnosti
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright (za scraping)
RUN playwright install chromium
RUN playwright install-deps chromium

COPY . .

EXPOSE 8000
