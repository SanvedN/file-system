# ---- Base Image ----
FROM python:3.11-slim AS base

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc libpq-dev curl build-essential \
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

# Copy dependencies
COPY pyproject.toml poetry.lock* requirements.txt* /app/

# Install dependencies
RUN uv pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY ./src /app/src

# FastAPI runtime settings
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Run the app
CMD ["uvicorn", "file_service.app:app", "--host", "0.0.0.0", "--port", "8000"]
