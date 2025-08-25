# Dockerfile - VERSIÓN CORREGIDA Y FINAL

# --- Etapa 1: Builder ---
FROM python:3.12-slim as builder

ENV POETRY_VERSION=1.8.2
RUN pip install "poetry==$POETRY_VERSION"
RUN poetry config virtualenvs.in-project true
WORKDIR /app
COPY poetry.lock pyproject.toml ./
RUN poetry install --no-interaction --no-ansi --no-dev --no-root


# --- Etapa 2: Final ---
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv .venv

COPY . .

ENV PYTHONPATH=/app

# Crea un usuario no-root para mayor seguridad
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

EXPOSE 8000

# CAMBIO 3: Ajustamos el comando para que apunte a 'src.main:app'
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]