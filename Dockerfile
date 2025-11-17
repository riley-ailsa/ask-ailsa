# Multi-stage build for Grant Discovery API
# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/

# Ensure PATH includes local Python binaries
ENV PATH=/root/.local/bin:$PATH

# Create volume mount point for database
VOLUME ["/app/data"]

# Environment variables (override with docker-compose or -e flags)
ENV DB_PATH=/app/data/grants.db
ENV OPENAI_API_KEY=""
ENV PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose API port
EXPOSE 8000

# Run API server
CMD ["sh", "-c", "python3 -m uvicorn src.api.server:app --host 0.0.0.0 --port ${PORT}"]
