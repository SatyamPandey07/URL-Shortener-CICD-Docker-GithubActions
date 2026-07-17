# ShortLink 🔗

A minimal, self-hosted URL shortener built with **FastAPI**, **PostgreSQL**, and **Python**.

ShortLink is the foundation for an 8-PR series that builds a production-grade CI/CD pipeline on top of this core app. Each pull request layers in one more piece of the deployment story — Docker production builds, automated testing in CI, container registry publishing, staged deployments, security scanning, and monitoring.

---

## Features (PR #1)

| Feature | Details |
|---|---|
| **Shorten** | `POST /shorten` — accepts a long URL, generates a 6-character base-62 short code |
| **Redirect** | `GET /{code}` — 302-redirects to the original URL; increments click count |
| **Homepage** | `GET /` — simple web UI, paste a URL, get your short link, copy button included |
| **Validation** | Rejects empty or non-HTTP(S) URLs with a clear error message |
| **Health check** | `GET /health` — returns `{"status": "ok"}` for deployment pipeline health probes |
| **Click tracking** | `click_count` incremented on every redirect |
| **Database** | PostgreSQL via SQLAlchemy ORM; schema managed by Alembic |

---

## Tech Stack

- **Backend**: Python 3.12 + FastAPI + Uvicorn
- **Database**: PostgreSQL 16 + SQLAlchemy 2.0 + Alembic
- **Frontend**: Jinja2 server-rendered HTML (no JS framework)
- **Tests**: pytest + FastAPI TestClient (SQLite in-memory, no Postgres needed)
- **Local dev**: Docker Compose

---

---

## Quick Start — Local Development (Docker Compose)

> **This is the dev-only setup.** Hot-reload is on, the source directory is
> volume-mounted, and the app runs as root. For production use, see the
> [Production Build](#production-build) section below.

**Prerequisites**: Docker and Docker Compose installed.

```bash
# 1. Clone the repository
git clone https://github.com/SatyamPandey07/URL-Shortener-CICD-Docker-GithubActions.git
cd URL-Shortener-CICD-Docker-GithubActions

# 2. Start the app + database
docker compose up --build

# 3. Open in your browser
open http://localhost:8000
```

`docker compose up` will:
1. Start a PostgreSQL container and wait until it's healthy
2. Run `alembic upgrade head` to apply the database schema
3. Start the FastAPI app on port 8000 with hot-reload enabled

---

## Quick Start (Local Python)

**Prerequisites**: Python 3.12+, a running PostgreSQL instance.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure the database connection
cp .env.example .env
# Edit .env — set DATABASE_URL and APP_BASE_URL

# 4. Apply database migrations
alembic upgrade head

# 5. Run the development server
uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Production Build

The production `Dockerfile` uses a **multi-stage build** to produce a minimal,
hardened image. This is what gets published to the container registry and
deployed to staging and production in later PRs.

### Why multi-stage?

| Concern | How the production Dockerfile handles it |
|---|---|
| **Image size** | `builder` stage compiles deps with gcc; `runtime` stage copies only the installed packages — no compiler, no pip, no build tools in the final image |
| **Attack surface** | Fewer packages = fewer CVE exposure points; `libpq5` runtime lib only, no `libpq-dev` |
| **Non-root user** | App runs as `appuser` (UID 1001) — root compromise inside the container cannot escalate to host root |
| **Secret hygiene** | `.dockerignore` excludes `.env` and all `*.env` files so secrets never bake into an image layer |
| **Health probes** | `HEALTHCHECK` polls `GET /health` every 30s; orchestrators (Docker Swarm, Kubernetes, Render) use this to decide if a container is ready |
| **Config from env** | `DATABASE_URL`, `PORT`, `APP_BASE_URL`, `WORKERS` all come from env — the same image runs in local, staging, and production with different configs |

### Build and run the production image

```bash
# Build the image (tagged for local testing)
docker build -t shortlink:prod .

# Inspect the final image size
docker image inspect shortlink:prod --format '{{.Size}}' | numfmt --to=iec

# Run against a local Postgres (adjust DATABASE_URL for your setup)
docker network create shortlink-net

docker run -d \
  --name shortlink-db \
  --network shortlink-net \
  -e POSTGRES_USER=shortlink \
  -e POSTGRES_PASSWORD=shortlink \
  -e POSTGRES_DB=shortlink \
  postgres:16-alpine

docker run -d \
  --name shortlink-prod \
  --network shortlink-net \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://shortlink:shortlink@shortlink-db:5432/shortlink \
  -e APP_BASE_URL=http://localhost:8000 \
  shortlink:prod

# Verify it is healthy
docker ps                              # check STATUS column shows (healthy)
curl http://localhost:8000/health      # {"status": "ok"}
curl http://localhost:8000/            # homepage HTML

# Clean up
docker rm -f shortlink-prod shortlink-db
docker network rm shortlink-net
```

### Verify non-root execution

```bash
docker run --rm shortlink:prod whoami   # appuser
```

### Image layers

The `Dockerfile` is structured so that the **dependency layer is cached**
independently of the application source. Rebuilding after a pure code change
(no `requirements.txt` change) re-uses the cached dependency layer and
completes in seconds instead of minutes.

---

## Running Tests

Tests use SQLite in-memory — **no PostgreSQL required**.

```bash
# Install dependencies (if not already done)
pip install -r requirements.txt

# Run the test suite
pytest -v
```

---

## Project Structure

```
.
├── app/
│   ├── main.py              # FastAPI app and all routes
│   ├── models.py            # SQLAlchemy ORM model (Link)
│   ├── database.py          # Engine, session factory, Base
│   ├── schemas.py           # Pydantic request/response models
│   ├── crud.py              # Database helper functions
│   └── shortener.py         # Base-62 code generator
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py
├── templates/
│   ├── index.html           # Homepage
│   └── 404.html             # 404 page
├── tests/
│   ├── conftest.py          # Fixtures and SQLite override
│   └── test_api.py          # API endpoint tests
├── Dockerfile               # ← Multi-stage production image (PR #2)
├── docker-entrypoint.sh     # ← Runs migrations then starts uvicorn (PR #2)
├── docker-compose.yml       # Local dev only (hot-reload, volume mount)
├── .dockerignore            # ← Keeps secrets and junk out of images (PR #2)
├── requirements.txt
├── alembic.ini
└── .env.example
```

---

## API Reference

### `GET /health`
Returns `{"status": "ok"}`. Used by deployment pipeline health probes.

### `POST /shorten`
**Content-Type**: `application/x-www-form-urlencoded` or `application/json`

| Field | Type | Description |
|---|---|---|
| `url` | string | The long URL to shorten (must start with `http://` or `https://`) |

**Success (200)**:
```json
{
  "short_url": "http://localhost:8000/aB3xZ9",
  "code": "aB3xZ9",
  "original_url": "https://www.example.com/long/path"
}
```

**Error (422)** — invalid or empty URL:
```json
{ "detail": "URL must start with http:// or https://" }
```

### `GET /{code}`
302-redirects to the original URL, or renders a 404 page if the code is unknown.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://shortlink:shortlink@localhost:5432/shortlink` | PostgreSQL connection string |
| `APP_BASE_URL` | `http://localhost:8000` | Base URL prepended to generated short codes |

Copy `.env.example` to `.env` and adjust for your environment.

---

## Roadmap

This repository is being built incrementally across 8 pull requests. ShortLink is the app; the CI/CD pipeline is the real project.

| PR | Branch | Focus |
|---|---|---|
| **#1** ✅ | `feat/core-app` | Core FastAPI app, PostgreSQL, Alembic, pytest, docker-compose |
| **#2 (this PR)** | `feat/production-docker` | Multi-stage Dockerfile, non-root user, HEALTHCHECK, .dockerignore |
| #3 | `feat/ci-pipeline` | GitHub Actions CI: lint, test, build Docker image on every push |
| #4 | `feat/registry-publish` | Publish container image to GitHub Container Registry (GHCR) on merge to `develop` |
| #5 | `feat/staging-deploy` | Automated deploy to staging on merge to `develop`; integration smoke tests |
| #6 | `feat/production-deploy` | Deploy to production on merge to `main` with a manual approval gate |
| #7 | `feat/security-scanning` | Container vulnerability scanning (Trivy), dependency auditing (pip-audit) |
| #8 | `feat/monitoring` | Health-check alerts, uptime monitoring, basic observability |

---

## Contributing

This project uses **Conventional Commits**. Please format commit messages as:

```
type(scope): short description

Examples:
  feat(api): add rate limiting to POST /shorten
  fix(redirect): handle trailing slash in short codes
  chore: update dependencies
  docs: add deployment section to README
```

---

## License

MIT
