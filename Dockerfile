# ---- Stage 1: builder ----
FROM python:3.11-slim AS builder

ENV POETRY_VERSION=1.8.5 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

WORKDIR /app

# Install dependencies first (layer cache)
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

# ---- Stage 2: runtime ----
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy the virtualenv from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Activate the virtualenv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="src" \
    PYTHONUNBUFFERED=1

# Copy application code and assets
COPY src/ src/
COPY cli/ cli/
COPY assets/ assets/
COPY config/ config/

# Externalized configuration
ENV GOOGLE_API_KEY="" \
    ENVIRONMENT="production" \
    MOCK_MODE="true"

# Default reports output directory
RUN mkdir -p reports

CMD ["python", "cli/run_simulation.py"]
