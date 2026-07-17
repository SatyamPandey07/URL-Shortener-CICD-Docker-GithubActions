# Security Policy

## Vulnerability Vetting & Reporting

We take the security of **ShortLink** seriously. If you identify a security vulnerability in this project, please **do not open a public issue**. Instead, report it privately to the maintainer:

- **Contact**: `security@shortlink.dev` (or open a Private Vulnerability Report on GitHub)

Please include:
- A clear description of the vulnerability.
- Step-by-step reproduction instructions or a Proof of Concept (PoC).
- Potential impact (e.g. denial of service, data leakage).

We will acknowledge receipt of your report within 48 hours and coordinate a fix and release disclosure timeline.

---

## Security Automation & Defense-in-Depth

The ShortLink deployment pipeline implements a multi-layered security strategy to catch vulnerabilities at every stage of the lifecycle.

```
[ CodeQL SAST ] ──> [ Dependabot Audits ] ──> [ Trivy Container Scan ] ──> [ Production Manual Gate ]
```

### 1. Static Application Security Testing (SAST)
- **Tool**: GitHub CodeQL ([codeql.yml](file:///.github/workflows/codeql.yml))
- **Scope**: Scans the Python source code for logic bugs, SQL injection patterns, insecure libraries, and path traversal vulnerabilities.
- **Frequency**: Runs on every pull request targeting `develop` or `main`, on pushes, and on a weekly schedule.

### 2. Dependency Auditing
- **Tool**: Dependabot ([dependabot.yml](file:///.github/dependabot.yml))
- **Scope**: Audits Python packages in `requirements.txt` and GitHub Actions referenced in workflows.
- **Frequency**: Checks weekly. Automatically opens PRs on the `develop` branch if security patches or version updates are available.

### 3. Container Image Hardening & Verification
- **Tools**: Multi-stage Dockerfile ([Dockerfile](file:///Dockerfile)) & Trivy Scanner ([publish-image.yml](file:///.github/workflows/publish-image.yml))
- **Hardening**:
  - The final image uses `python:3.12-slim` containing only runtime libraries (e.g. `libpq5`), leaving compilers and dev tools completely out.
  - Runs as an unprivileged, non-root user (`appuser` UID 1001) to prevent container escape host escalation.
- **Active Scanning**:
  - Before pushing the built image to GHCR, Trivy scans the container's OS and Python packages.
  - If any **CRITICAL** vulnerability is detected, the CD pipeline fails instantly, blocking publication to the registry.

### 4. Human-in-the-Loop Environment Promotion
- **Mechanism**: GitHub Environment Gates ([deploy-production.yml](file:///.github/workflows/deploy-production.yml))
- **Scope**: Production deployments require manual approval from a designated reviewer in the Actions UI. This ensures that no software goes live without explicit human verification of staging test logs and release notes.
