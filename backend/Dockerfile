# Backend de la Plataforma Hídrica Zulia (FastAPI + ML). Contexto de construcción: raíz del repositorio.
#   docker build -f backend/Dockerfile -t plataforma-hidrica-backend .
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Librerías del sistema: cliente de PostgreSQL (respaldos) y dependencias de rasterio/matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client libexpat1 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv

WORKDIR /app
# Dependencias primero (capa cacheable)
COPY ml/pyproject.toml ml/uv.lock ml/README.md* /app/ml/
COPY ml/src /app/ml/src
COPY backend/pyproject.toml backend/uv.lock /app/backend/
WORKDIR /app/backend
RUN uv sync --frozen --no-dev --no-install-project

# Código y datos versionados (geometrías OSM, configuración de ML)
COPY ml /app/ml
COPY backend /app/backend
RUN uv sync --frozen --no-dev

# Usuario sin privilegios
RUN useradd --create-home --uid 1000 hidrica && mkdir -p /app/ml/models /app/ml/reports && chown -R hidrica /app/ml/models /app/ml/reports
USER hidrica

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)"

# Aplica migraciones y arranca. --proxy-headers: IP real del cliente detrás del proxy (bitácora y límite de intentos)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_WORKERS:-2} --proxy-headers --forwarded-allow-ips='*'"]
