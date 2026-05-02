# ── Stage 1: Build dependencies ────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Production image ──────────────────────────────────────────
FROM python:3.11-slim

# Install only what's needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo libwebp7 libfreetype6 && \
    rm -rf /var/lib/apt/lists/*

# Copy installed Python packages
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application code
COPY app/ app/
COPY config/ config/
COPY migrations/ migrations/

# Create data directory
RUN mkdir -p /app/data /app/app/static/uploads

# Non-root user
RUN useradd -m -r -s /bin/bash zcore && chown -R zcore:zcore /app
USER zcore

# Environment
ENV PYTHONUNBUFFERED=1 \
    ZCORE_DB_PATH=/app/data/zcore.db \
    ZCORE_HOST=0.0.0.0 \
    ZCORE_PORT=8000

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/')" || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
