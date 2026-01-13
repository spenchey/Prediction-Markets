# Dockerfile for Prediction Market Tracker
# Build version: 2026-01-13-v6 (inline startup)

FROM python:3.11-slim as builder
ARG CACHE_BUST=v6
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim as runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

ARG SRC_CACHE_BUST=v6
COPY src/ ./src/

RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8000
EXPOSE 8000

# Inline startup - no external script needed
CMD python -c "print('=== CONTAINER STARTING ==='); print('Python OK')" && \
    python -c "from fastapi import FastAPI; print('FastAPI OK')" && \
    echo "Starting uvicorn on port ${PORT:-8000}" && \
    uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
