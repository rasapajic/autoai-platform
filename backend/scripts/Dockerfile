FROM python:3.11-slim

WORKDIR /app

COPY scripts/requirements.txt /tmp/cron-requirements.txt
RUN pip install --no-cache-dir -r /tmp/cron-requirements.txt

COPY . /app/

# Import the actual cron module during build without executing a refresh.
RUN python -c "import runpy; runpy.run_path('/app/scripts/scraper.py', run_name='cron_import_check')"

# Only the guarded internal refresh client runs; missing configuration fails closed.
CMD ["python", "/app/scripts/scraper.py"]
