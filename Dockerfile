# Multi-stage Docker build for production-ready containers
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libmagic1 \
    libmagic-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set work directory
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/storage /app/logs && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose ports (will be overridden by specific services)
EXPOSE 8000

# Default command (will be overridden by specific services)
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]


# File Service specific stage
FROM base as file-service

# Set service-specific environment
ENV SERVICE_NAME=file_service
ENV SERVICE_PORT=8001

# Expose file service port
EXPOSE 8001

# Run file service
CMD ["python", "-m", "uvicorn", "src.file_service.app:app", "--host", "0.0.0.0", "--port", "8001"]


# Extraction Service specific stage
FROM base as extraction-service

# Set service-specific environment
ENV SERVICE_NAME=extraction_service
ENV SERVICE_PORT=8002

# Expose extraction service port
EXPOSE 8002

# Run extraction service
CMD ["python", "-m", "uvicorn", "src.extraction_service.app:app", "--host", "0.0.0.0", "--port", "8002"]


# API Gateway stage (optional)
FROM base as api-gateway

# Set service-specific environment
ENV SERVICE_NAME=api_gateway
ENV SERVICE_PORT=8000

# Expose API gateway port
EXPOSE 8000

# Run API gateway (placeholder - would implement gateway service)
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
