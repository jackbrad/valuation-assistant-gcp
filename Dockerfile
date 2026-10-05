# Appraisal-Grade Valuation AI Dockerfile for Google Cloud Run
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    APP_HOME=/app

WORKDIR $APP_HOME

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for dependency installation
RUN pip install --no-cache-dir uv

# Copy project definition and install dependencies
COPY pyproject.toml .
RUN uv pip compile pyproject.toml -o requirements.txt && uv pip install --system -r requirements.txt

# Copy application directories
COPY app/ ./app/
COPY clearline/ ./clearline/
COPY config/ ./config/
COPY valuation/ ./valuation/
COPY agent/ ./agent/
COPY pipeline/ ./pipeline/
COPY data_gen/ ./data_gen/

EXPOSE 8080

CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
