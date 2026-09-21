# ---------- build stage ----------
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- final stage ----------
FROM python:3.12-slim

# Security: run as non-root
RUN useradd -m -r appuser
WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=appuser:appuser . .

USER appuser
EXPOSE 8080

# Railway injects $PORT; fall back to 8080 locally / in docker-compose.
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 2 --timeout 30 --access-logfile - app:app