FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8000

# API plus guarded, manually triggered internal listing recovery.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
