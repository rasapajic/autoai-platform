FROM python:3.11-slim

WORKDIR /app

COPY . /app/

# Emergency legal-source freeze: this image must never fetch or update listings.
CMD ["python", "-c", "print('AutoAI external data updates are disabled')"]
