# ShortLink 🔗

[![CI](https://github.com/SatyamPandey07/URL-Shortener-CICD-Docker-GithubActions/actions/workflows/ci.yml/badge.svg)](https://github.com/SatyamPandey07/URL-Shortener-CICD-Docker-GithubActions/actions/workflows/ci.yml)

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

## Image Publishing

Continuous Delivery (CD) automatically builds, scans, and publishes the production container image to **GitHub Container Registry (GHCR)** on every push to the `develop` and `main` branches.

- **Registry Location**: [ghcr.io/satyampandey07/shortlink](https://github.com/SatyamPandey07/URL-Shortener-CICD-Docker-GithubActions/pkgs/container/shortlink)
- **Workflow Location**: [.github/workflows/publish-image.yml](file:///.github/workflows/publish-image.yml)

### Tagging Strategy

Every build is tagged with the **Git short SHA** (7-character commit hash) to ensure 100% traceability from running containers back to code changes. Additional branch-specific tags are applied automatically:

| Target Branch | Tags Applied | Purpose |
|---|---|---|
| `develop` | `staging-<short-sha>`, `<short-sha>` | Deployed automatically to the staging environment |
| `main` | `prod-<short-sha>`, `latest`, `<short-sha>` | Deployed to production |

### Vulnerability Gate (Trivy Scan)

To prevent security regressions, the publishing pipeline runs **Trivy** to scan the image's OS and language libraries before pushing:
1. The image is built and loaded into the local Docker runner.
2. Trivy scans the image for **CRITICAL** vulnerabilities.
3. If any critical vulnerabilities are found, the workflow **fails immediately** and halts the push, keeping insecure images completely out of the registry.
4. If the scan is clean, the image is pushed with all tags.

---

## Staging Deployment

Once the container image is successfully built and pushed to GHCR on the `develop` branch, the pipeline automatically triggers a deployment to the staging environment hosted on Render.

- **Staging URL**: `https://shortlink-staging.onrender.com` (Placeholder - to be finalized)
- **Workflow Location**: [.github/workflows/deploy-staging.yml](file:///.github/workflows/deploy-staging.yml)

### Deployment & Promotion Flow

The entire path from code merge to staging, and manually promoted production delivery:

```mermaid
graph TD
    subgraph Staging Pipeline
        A[Merge PR into develop] --> B[GHA: ci.yml Checks]
        B -->|Passed| C[GHA: publish-image.yml]
        C -->|Build & Scan Clean| D[Push staging-SHA to GHCR]
        D -->|workflow_run Completed| E[GHA: deploy-staging.yml]
        E -->|Trigger| F[Render Staging Deploy Hook]
        F -->|Poll /health every 10s| G{Staging Healthy?}
        G -->|Yes| H[Staging Deployment Successful]
        G -->|No after 2 min| I[Staging Deployment Failed]
    end

    subgraph Production Promotion
        J[Manual Merge develop into main] --> K[GHA: publish-image.yml]
        K -->|Build & Scan Clean| L[Push prod-SHA & latest to GHCR]
        L -->|workflow_run Completed| M[GHA: deploy-production.yml]
        M --> N{GitHub Environment: production Gate}
        N -->|Manual Reviewer Approved| O[Trigger Render Production Deploy Hook]
        N -->|Rejected / Timeout| P[Run Aborted]
        O -->|Poll /health every 10s| Q{Production Healthy?}
        Q -->|Yes| R[Production Deployment Successful]
        Q -->|No after 2 min| S[Production Deployment Failed / Alert]
    end
```

### Health Verification Gate

Unlike a blind webhook trigger, the deployment pipeline verifies that the staging application is online:
1. Calls the Render deploy hook using the `RENDER_STAGING_DEPLOY_HOOK` secret.
2. Registers a **Staging Environment** deployment in GitHub (visible in the repository's deployments history UI).
3. Polls the staging service's `/health` endpoint for up to **2 minutes** (12 attempts, 10s sleep).
4. If `/health` returns `200 OK`, the workflow marks the staging environment deployment as successful.
5. If the health check fails or times out, the workflow fails loudly, signaling deployment issues.

---

## Production Deployment

Deployments to the production environment are gated behind automated safety checks and a manual approval step. This ensures that environment promotion is a deliberate, human-reviewed action.

- **Production URL**: `https://shortlink-prod.onrender.com` (Placeholder - to be finalized)
- **Workflow Location**: [.github/workflows/deploy-production.yml](file:///.github/workflows/deploy-production.yml)

### Manual Approval Gate

The production deployment job uses GitHub Environments to implement approval rules:
1. When the `Publish Production Image` workflow succeeds on the `main` branch, the `Deploy to Production` workflow is triggered.
2. The deployment job references `environment: production`.
3. In the repository settings (`Settings -> Environments -> production`), a **Required Reviewer** is configured.
4. GitHub automatically pauses the job and sends a notification to the designated reviewer. No steps (including the webhook trigger) will run.
5. The reviewer reviews the staging verification status, checks the diff, and clicks **Approve** in the Actions UI.
6. Once approved, the job resumes, triggers the Render production web service via the `RENDER_PRODUCTION_DEPLOY_HOOK` secret, and begins health verification.

### Health Verification Gate

Just like staging, the production pipeline polls the production `/health` endpoint for up to **2 minutes** (12 attempts, 10s intervals) to confirm the new version is healthy and accepting traffic.

---

## Rollback Procedures

If a faulty deploy passes health checks but exhibits regressions in production, you can execute a manual rollback to the previous known-good state. Because our pipeline tags every container image with its unique Git commit SHA, rollbacks are precise, rapid, and do not require code changes or rebuilds.

### Steps to Roll Back (Render Web Service)

1. **Identify the Last Known-Good Commit SHA**:
   - Look at the git log or GitHub release history to locate the SHA of the previous successful deployment (e.g., `a1b2c3d`).
2. **Retrieve the Corresponding Image Tag**:
   - The corresponding production image in GHCR is tagged as `prod-a1b2c3d`.
3. **Point Render at the Previous Tag**:
   - Log into the Render Dashboard and navigate to the production web service.
   - Go to **Settings -> Docker Image URL**.
   - Change the tag from the failing commit SHA (or `latest`) to `prod-a1b2c3d` (e.g. `ghcr.io/satyampandey07/shortlink:prod-a1b2c3d`).
   - Click **Save Changes**.
4. **Trigger Redeployment**:
   - Click **Manual Deploy -> Clear Cache and Deploy** (or simply **Deploy Latest Commit** if the image URL is updated).
5. **Verify Health**:
   - Monitor the Render console logs and request `/health` locally to confirm the service reverted cleanly to the healthy state.

---

## Security Posture

We implement a defense-in-depth security model to ensure the software remains secure at rest, in transit, and during the deploy phase:

1. **Dependency Scanning (Dependabot)**: Automatically checks for Python library updates and GitHub Action deprecations weekly, raising PRs against the `develop` branch to remediate stale or vulnerable libraries.
2. **Container Image Scanning (Trivy)**: Scans compiled container images during the CD stage before registry publishing. Blocks pushed images immediately if any `CRITICAL` vulnerability is detected.
3. **Static Application Security Testing (CodeQL)**: Scans source code natively on GitHub for code smells, injections, and vulnerabilities on PRs and weekly scheduled scans.
4. **Environment Gate (Required Reviewers)**: Production deployment requires an explicit manual sign-off by a designated maintainer, protecting the production site from unintentional promotions.

For detailed instructions on private reporting of vulnerabilities, refer to [SECURITY.md](file:///SECURITY.md).

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
├── .github/
│   ├── workflows/
│   │   ├── ci.yml            # GHA CI: lint, test, build (PR #3)
│   │   ├── publish-image.yml # GHA CD: build, Trivy scan, push to GHCR (PR #4)
│   │   ├── deploy-staging.yml # GHA CD: trigger Render deploy & poll health (PR #5)
│   │   ├── deploy-production.yml # GHA CD: manual approval production deploy (PR #6)
│   │   └── codeql.yml        # ← GHA Security: CodeQL static analysis (PR #7)
│   └── dependabot.yml        # ← Dependency update scheduler (PR #7)
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
├── docs/
│   ├── PIPELINE.md          # Walkthrough of the CI/CD pipeline (PR #8)
│   └── RUNBOOK.md           # Operational runbook & rollback instructions (PR #8)
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
├── SECURITY.md              # ← Security Policy & Reporting Guide (PR #7)
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
| **#2** ✅ | `feat/production-docker` | Multi-stage Dockerfile, non-root user, HEALTHCHECK, .dockerignore |
| **#3** ✅ | `feat/ci-pipeline` | GitHub Actions CI: lint, test, build Docker image on every push |
| **#4** ✅ | `feat/image-publishing` | Publish container image to GitHub Container Registry (GHCR) on merge to `develop` |
| **#5** ✅ | `feat/staging-deploy` | Automated deploy to staging on merge to `develop`; integration smoke tests |
| **#6** ✅ | `feat/production-deploy` | Deploy to production on merge to `main` with a manual approval gate |
| **#7** ✅ | `feat/security-automation` | Container vulnerability scanning (Trivy), dependency auditing (pip-audit), CodeQL SAST, Dependabot |
| **#8 (this PR)** | `feat/final-polish` | Structured logging middleware, pipeline documentation, runbook, live staging and production URLs |

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
