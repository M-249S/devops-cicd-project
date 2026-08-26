# DevSecOps CI/CD Pipeline

[![CI Pipeline](https://github.com/M-249S/devops-cicd-project/actions/workflows/ci.yml/badge.svg)](https://github.com/M-249S/devops-cicd-project/actions/workflows/ci.yml)

A small Flask API wrapped in a security-hardened Docker image, shipped through
a six-stage CI/CD pipeline that lints, tests, scans, hardens, and publishes
the image automatically on every push — and refuses to publish anything that
fails a security check.

This project was built to demonstrate practical DevSecOps skills: not just
"CI/CD that works," but a pipeline that treats security as a required gate
rather than an afterthought.

## Why this project

Most beginner CI/CD demos stop at "build → test → deploy." This one adds the
"Sec" in DevSecOps deliberately, at every layer:

- Static code analysis on the application itself
- Dependency and OS-package vulnerability scanning
- Secret-leak detection across the full Git history
- A hardened container that runs as a non-root user with a read-only
  filesystem
- Secrets injected at runtime only, never baked into the image
- A pipeline that **fails closed**: if any security check fails, the image
  is never pushed to the registry

## Architecture

```
Client → Flask app (Gunicorn) → Docker container → GitHub Container Registry
```

The app itself is intentionally simple (three endpoints) — the point of this
project is the pipeline and the security posture around it, not the
application logic.

## Endpoints

| Route             | Method | Purpose                                                      |
|--------------------|--------|---------------------------------------------------------------|
| `/`                 | GET    | Welcome message                                               |
| `/health`           | GET    | Liveness check, used by the Docker `HEALTHCHECK`              |
| `/config-status`    | GET    | Confirms whether `API_KEY` is configured, **without** ever revealing its value |

## Tech stack

- **App**: Python 3.12, Flask, Gunicorn
- **Container**: Docker, non-root user, read-only root filesystem
- **CI/CD**: GitHub Actions
- **SAST**: [Bandit](https://bandit.readthedocs.io/)
- **Secret scanning**: [Gitleaks](https://github.com/gitleaks/gitleaks)
- **Vulnerability scanning**: [Trivy](https://trivy.dev/) (filesystem + image)
- **Registry**: GitHub Container Registry (GHCR)
- **Testing**: pytest

## CI/CD pipeline

Every push to `main` runs six stages. Later stages only run if earlier ones
pass — a security failure anywhere stops the image from ever reaching the
registry.

```
Lint ──▶ Test ──▶ ┌ SAST (Bandit)            ┐
                   ├ Secret Scan (Gitleaks)  ├──▶ Build → Scan → Push
                   └ Dependency Scan (Trivy) ┘
```

| Stage | Tool | What it checks |
|---|---|---|
| **Lint** | flake8 | Code style (PEP 8) |
| **Test** | pytest | 10 unit tests covering all endpoints, error handling, and secret-safety |
| **SAST** | Bandit | Insecure code patterns in the application source |
| **Secret Scan** | Gitleaks | Hardcoded credentials anywhere in the Git history |
| **Dependency Scan** | Trivy (filesystem) | Known CVEs in Python dependencies and OS packages |
| **Build & Push** | Docker Buildx + Trivy (image) | Builds the image, scans the *built* image for CVEs, runs a smoke test with a read-only filesystem and an injected secret, and only then pushes to GHCR |

The pipeline is configured to `exit-code: 1` on any HIGH or CRITICAL Trivy
finding — the build stage genuinely cannot succeed while a known,
fixable vulnerability is present.

## Security decisions and trade-offs

A few choices worth calling out explicitly, since the reasoning matters more
than the line of YAML:

- **Read-only root filesystem.** The container runs with `--read-only` and
  only `/tmp` mounted as writable (`tmpfs`). Gunicorn's worker heartbeat
  files are pointed at `/dev/shm` for the same reason. If the app were ever
  compromised, an attacker gets nowhere writing to disk.
- **Secrets are runtime-only.** `API_KEY` is injected via `-e` at container
  start, sourced from GitHub Secrets in CI. It is never present in a Docker
  layer, so it can't be extracted from the image itself — only from a
  running container with the right access.
- **Base image patched, not just pinned.** `apt-get upgrade` runs during the
  build to pull in OS-level CVE fixes (e.g. a HIGH-severity OpenSSL CVE
  found by Trivy during development, see commit history) that lag behind
  the upstream `python:3.12-slim` tag.
- **`trivy-action` is currently pinned to `@master`, not a released tag.**
  This is a known trade-off, not an oversight — see the `TODO` in
  `ci.yml`. Pinning to a commit SHA is the more correct approach for
  supply-chain security and is the next planned improvement.
- **GHCR over Docker Hub.** No manually managed registry credentials —
  authentication uses the automatically scoped `GITHUB_TOKEN`, reducing the
  number of long-lived secrets in the project.

## Running locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

pytest tests/ -v          # run the test suite
flake8 app.py tests/ --max-line-length=100 --extend-ignore=E501
bandit -r app.py -f screen --severity-level medium
```

## Running with Docker

```bash
docker build -t devops-demo:latest .

docker run -d --name devops-demo \
  --read-only --tmpfs /tmp \
  -p 5000:5000 \
  -e API_KEY=your-local-value \
  devops-demo:latest

curl http://localhost:5000/health
```

## Secrets setup (for anyone forking this repo)

1. Copy `.env.example` to `.env` and fill in a local value — `.env` is
   git-ignored and never committed.
2. For CI, add the same key under **Settings → Secrets and variables →
   Actions → New repository secret** in GitHub. The pipeline reads it as
   `${{ secrets.API_KEY }}`.

## What I'd add next

- Pin `trivy-action` to a commit SHA instead of `@master`
- Pin the base image by digest, with Dependabot/Renovate to bump it
- Terraform to provision the deployment target (EC2/ECS)
- SBOM generation as a pipeline artifact

---

Built as part of a self-directed DevSecOps upskilling plan, applying a
software engineering + IT security background to hands-on CI/CD practice.