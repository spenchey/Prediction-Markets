# Dockerfile for Prediction Market Tracker
# Build version: 2026-01-13-v7 (single stage, minimal)

FROM python:3.11-slim

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Environment
ENV PYTHONUNBUFFERED=1

# Railway sets PORT environment variable
EXPOSE 8000

# No CMD - Railway uses Procfile instead
