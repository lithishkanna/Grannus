# Multi-Stage Dockerfile for Grannus RuralCare AI Backend
# Base: Python 3.12 Slim (Linux)

# Stage 1: Build Dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Hardened Runtime
FROM python:3.12-slim AS runner

WORKDIR /app

# Install runtime system libraries for audio decoding
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Security: Non-root user
RUN groupadd -g 1001 grannus && \
    useradd -u 1001 -g grannus -s /bin/bash -m grannususer

COPY --from=builder /install /usr/local
COPY . /app

# Ensure correct permissions
RUN chown -R grannususer:grannus /app

USER grannususer

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
