# ShortLink Operational Runbook

This runbook provides step-by-step operational instructions for diagnosing failures, reviewing deployment logs, and rolling back production deployments.

---

## 1. Checking Service Health & Diagnosis

If the application is suspected to be down or returning errors, follow these steps:

### Step 1: Query the Health Check Endpoint
Run a request to the health endpoint of the target environment:

```bash
# Check Staging
curl -i https://shortlink-staging.onrender.com/health

# Check Production
curl -i https://shortlink-prod.onrender.com/health
```

- **Healthy Response**: `HTTP/1.1 200 OK` with body `{"status": "ok"}`
- **Unhealthy Response**: Anything else (e.g. `502 Bad Gateway`, `500 Internal Server Error`, or connection timeout) indicates an application crash or database connection failure.

### Step 2: Inspect Application Container Logs
Log into the Render Dashboard:
1. Navigate to the **ShortLink Staging** or **ShortLink Production** web service page.
2. Click the **Logs** tab in the sidebar.
3. Check for recent traceback logs:
   - **Database Connection Errors**: Look for `psycopg2.OperationalError` or connection timeouts. Check if the database credentials in environment variables match.
   - **Startup Crashes**: Check for Python SyntaxErrors or missing module imports.

---

## 2. Reviewing GitHub Actions Logs

If a CI/CD build fails:
1. Navigate to the repository page on GitHub.
2. Click the **Actions** tab at the top.
3. Select the failed workflow run (marked with a red cross `❌`).
4. Click on the failing job (e.g., `Test (pytest + Postgres)` or `Verify Production Deployment Health`) in the sidebar.
5. Expand the failing step to read the exact terminal output:
   - **Linting failures**: Inspect the `Run ruff` logs to see files with style violations or unused imports.
   - **Test failures**: Scroll to the bottom of the `Run pytest` step to read failed assertions or tracebacks.
   - **Trivy failures**: Check the `Run Trivy vulnerability scanner` step for lists of detected vulnerabilities.
   - **Health check timeouts**: If the deployment step failed, review the `Verify Deployment Health` loop output to see what status codes the app returned during boot.

---

## 3. Rollback Procedures (Production Emergency)

If a bad deployment is approved and passes the basic `/health` check but contains hidden regressions, execute a manual rollback immediately.

**Concept**: Do NOT push code changes or revert commits in git during an outage. Instead, instruct Render to deploy the previous known-good Docker image by pointing it at the corresponding Git commit SHA tag.

### Step-by-Step Rollback via Render Dashboard

1. **Locate the Last Known-Good Commit SHA**:
   - Go to the repository's commits page on GitHub or the release list.
   - Copy the 7-character Git short SHA of the last stable build (e.g., `a86a92d`).
2. **Retrieve the Image Tag**:
   - The CD pipeline publishes every built image to GHCR tagged with `prod-<sha>`. The rollback target image is:
     `ghcr.io/satyampandey07/shortlink:prod-a86a92d`
3. **Update Render Image settings**:
   - Navigate to the **ShortLink Production** service settings on Render.
   - Go to **Settings -> Docker Image URL**.
   - Change the image tag from `latest` or the failing commit tag to the target tag:
     `ghcr.io/satyampandey07/shortlink:prod-a86a92d`
   - Click **Save Changes**.
4. **Deploy the Rollback**:
   - Render will automatically trigger a new deployment pulling the specific container image tag from GHCR.
   - If auto-deploy doesn't trigger, click **Manual Deploy -> Deploy Latest Commit** (or **Deploy from Image**).
5. **Verify Reversion**:
   - Monitor Render logs as the healthy image boots up.
   - Query `/health` to confirm the service reports online:
     `curl -i https://shortlink-prod.onrender.com/health`

### Post-Rollback Steps
Once the production site is restored:
1. Revert or patch the bad code on a local branch.
2. Open a PR to `develop` to merge the fix.
3. Resume the normal pipeline flow. Once verified in staging, merge `develop` to `main` and approve the new release tag.
