# Dockerfile for Prediction Market Tracker
# Build version: 2026-01-13-v5 (debug startup)

# ============================================
# Stage 1: Builder
# ============================================
FROM python:3.11-slim as builder

ARG CACHE_BUST=2026-01-13-v5

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================
# Stage 2: Runtime
# ============================================
FROM python:3.11-slim as runtime

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Force cache invalidation for src copy
ARG SRC_CACHE_BUST=2026-01-13-v5

# Copy application code
COPY src/ ./src/
COPY run.py .
COPY start.sh .

# Make start script executable
RUN chmod +x start.sh

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Expose port
EXPOSE 8000

# NO Docker healthcheck - let Railway handle it
# This prevents double health checks that might cause issues

# Start command - use the debug script
CMD ["/bin/bash", "./start.sh"]
