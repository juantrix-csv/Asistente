FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY apps ./apps
COPY packages ./packages

ENV PYTHONPATH=/app

CMD ["python", "-m", "apps.worker.app.main"]
