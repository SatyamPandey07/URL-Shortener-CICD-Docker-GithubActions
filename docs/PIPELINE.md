# ShortLink CI/CD Pipeline Walkthrough

This document outlines the automated pipeline that verifies, builds, and deploys the **ShortLink** application. It is written as a non-technical walkthrough to explain how code changes make their way safely from a developer's computer to the live website.

---

## High-Level Pipeline Architecture

The pipeline consists of three separate automated phases, orchestrated on GitHub:

```
[ Merge PR to develop ] ──> [ GHA CI: ci.yml ] ──> [ GHA CD: publish-image.yml ] ──> [ GHA CD: deploy-staging.yml ]
                                                                                                 │
                                                                                       (Staging verification ok)
                                                                                                 │
                                                                                                 ▼
[ Manual Merge to main ] ──> [ GHA CD: publish-image.yml ] ──> [ GHA CD: deploy-production.yml ] (requires manual approval)
```

---

## Phase 1: Continuous Integration (CI)
- **Workflow File**: `.github/workflows/ci.yml`
- **When it runs**: Every time a developer creates a Pull Request (PR) or pushes code changes to any branch.
- **What it checks**:
  1. **Code Linting & Formatting**: Checks if the Python code has syntax issues, unused imports, or bad code formatting styles (using a linter called `ruff`).
  2. **Automated Testing**: Runs our test suite (9 test cases) against a real, isolated PostgreSQL database container. This ensures database integrations work and verifies features like shortening links, redirections, and URL validation.
  3. **Code Coverage**: Enforces that at least **85%** of the codebase is covered by automated tests. If coverage falls below 85%, the build fails.
  4. **Docker Compilation**: Builds the production Docker container image locally to verify it compiles without errors.
- **Goal**: Catch errors early. Developers are notified immediately in their PR if code is broken.

---

## Phase 2: Continuous Delivery (CD) — Image Publishing
- **Workflow File**: `.github/workflows/publish-image.yml`
- **When it runs**: When code is successfully merged into `develop` or `main`.
- **What it does**:
  1. **Docker Compilation**: Compiles the final production container image.
  2. **Vulnerability Quality Gate (Trivy Scan)**: Before the image is published, an automated scanner named **Trivy** inspects the container's operating system and libraries for security vulnerabilities.
     - **If a CRITICAL vulnerability is found**: The workflow fails immediately, and the container is blocked from being published.
     - **If the scan is clean**: The workflow proceeds to publish the image to the **GitHub Container Registry (GHCR)**.
  3. **Tagging Strategy**:
     - Pushes to `develop` tag the image as `staging-<short-sha>` and `<short-sha>`.
     - Pushes to `main` tag the image as `prod-<short-sha>`, `latest`, and `<short-sha>`.

---

## Phase 3: Staging Deployment
- **Workflow File**: `.github/workflows/deploy-staging.yml`
- **When it runs**: Automatically runs *after* Phase 2 completes successfully on the `develop` branch.
- **What it does**:
  1. **Deployment Trigger**: Calls a secure deploy hook webhook provided by our staging hosting environment (Render).
  2. **Staging Environment**: Pulls the new `staging-<short-sha>` container image and starts it up.
  3. **Health Verification Loop**: The pipeline active-polls the staging website's `/health` endpoint for up to **2 minutes**.
     - If the service responds with `200 OK`, the deployment is marked successful.
     - If the service fails to start or responds with errors, the pipeline fails loudly.

---

## Phase 4: Production Deployment (Manual Approval Gate)
- **Workflow File**: `.github/workflows/deploy-production.yml`
- **When it runs**: Automatically runs *after* Phase 2 completes successfully on the `main` branch.
- **The Core Control (Why Staging differs from Production)**:
  - While code changes deploy automatically to staging for evaluation, we do *not* automatically deploy to production.
  - **Required Reviewer Gate**: This workflow references the `production` environment in GitHub. In our repository settings, the production environment requires manual sign-off.
  - **The Pause**: The pipeline pauses execution at the start of the deployment phase. GitHub alerts the project maintainer to review the pending release.
  - **The Approval**: Once the maintainer approves the release in the Actions UI, the pipeline triggers the production deploy hook on Render.
  - **Health Verification**: Just like staging, it polls the production `/health` endpoint for up to 2 minutes to confirm the site is healthy and active.
- **Goal**: Minimize risks by keeping a human-in-the-loop decision safeguard for production releases.
