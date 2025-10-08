# ---- Base builder stage ----
FROM python:3.11-slim AS builder

WORKDIR /app

# System build dependencies (only in builder)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev build-essential curl \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Install uv globally (just once)
RUN pip install uv

# Create a venv using uv
RUN uv venv /app/.venv

# Activate venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

# Add `src` to PYTHONPATH
ENV PYTHONPATH=/app/src

# Copy only dependency files to leverage cache
COPY pyproject.toml poetry.lock* requirements.txt* /app/

# Install Python dependencies into the venv
RUN uv pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . /app

# Create storage and temp directories
RUN mkdir -p /app/storage /app/temp

# ---- Final runtime image ----
FROM python:3.11-slim AS app

WORKDIR /app

# Install tesseract again only if needed at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment and app from builder
COPY --from=builder /app /app

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app/src

EXPOSE 8000 8001 8002

# Default entrypoint for uvicorn (gateway)
CMD ["python", "run.py"]
