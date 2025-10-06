# ---- Base Image ----
FROM python:3.11-slim AS base

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc libpq-dev curl build-essential \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Create a virtual environment with uv
RUN uv venv /app/.venv

# Activate venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Add `src` to PYTHONPATH so Python can find modules
ENV PYTHONPATH=/app/src

COPY pyproject.toml poetry.lock* requirements.txt* /app/

# Install dependencies
RUN uv pip install --no-cache-dir -r requirements.txt

COPY . /app

# FastAPI runtime settings
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Default to gateway; compose overrides for microservices
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
