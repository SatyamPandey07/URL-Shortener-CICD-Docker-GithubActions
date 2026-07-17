# =============================================================================
# STAGE 1 — builder
# Full dependencies including build tools. Nothing from this stage ships
# in the final image.
# =============================================================================
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build-time system deps (gcc + libpq-dev needed to compile psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps into an isolated prefix so we can COPY just the
# installed packages into the final stage without pip itself.
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# =============================================================================
# STAGE 2 — runtime
# Only what the app needs to *run*. No gcc, no pip, no build artifacts.
# =============================================================================
FROM python:3.12-slim AS runtime

# Install only the runtime system library for psycopg2 (no compiler needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
 && rm -rf /var/lib/apt/lists/* \
 && apt-get clean

# ── Non-root user ─────────────────────────────────────────────────────────────
# Running as root inside a container gives an attacker root on the host if
# they escape the container. Use a dedicated unprivileged user instead.
RUN groupadd --gid 1001 appgroup \
 && useradd --uid 1001 --gid appgroup --no-create-home --shell /sbin/nologin appuser

WORKDIR /app

# Copy installed Python packages from the builder stage
COPY --from=builder /install /usr/local

# Copy application source (owned by appuser, not root)
COPY --chown=appuser:appgroup . .

# Switch to the non-root user for all subsequent commands and at runtime
USER appuser

# ── Configuration ─────────────────────────────────────────────────────────────
# All config comes from environment variables — no hardcoded values.
# The same image runs in local, staging, and production with different envs.
#
# Required at runtime:
#   DATABASE_URL   e.g. postgresql://user:pass@host:5432/dbname
#
# Optional:
#   PORT           defaults to 8000
#   APP_BASE_URL   defaults to http://localhost:${PORT}
#   WORKERS        number of uvicorn workers (default: 1)

ENV PORT=8000 \
    WORKERS=1 \
    APP_BASE_URL=http://localhost:8000

EXPOSE ${PORT}

# ── Health check ──────────────────────────────────────────────────────────────
# Docker (and Kubernetes) use this to decide whether the container is ready
# to serve traffic. Probes GET /health every 30s; 3 consecutive failures
# mark the container unhealthy and trigger a restart in orchestration.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" \
    || exit 1

# ── Entrypoint ────────────────────────────────────────────────────────────────
# Uses the entrypoint script which runs Alembic migrations before starting
# the server, so the DB schema is always up to date on deploy.
COPY --chown=appuser:appgroup docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--no-access-log"]
