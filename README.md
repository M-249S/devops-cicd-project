# DevSecOps CI/CD Pipeline

![CI Pipeline](https://github.com/M-249S/devops-cicd-project/actions/workflows/ci.yml/badge.svg)

A small Flask API wrapped in a security-hardened Docker image, shipped through a seven-stage CI/CD pipeline that lints, tests, scans, hardens, and publishes the image automatically on every push — and refuses to publish anything that fails a security check.

This project was built to demonstrate practical DevSecOps skills: not just "CI/CD that works," but a pipeline that treats security as a required gate rather than an afterthought. See [SECURITY.md](SECURITY.md) for how the controls map to the OWASP Top 10:2025, including what is not covered.

## Why this project

Most beginner CI/CD demos stop at "build → test → deploy." This one adds the "Sec" in DevSecOps deliberately, at every layer:

- Static code analysis on the application itself
- Dependency and OS-package vulnerability scanning
- Secret-leak detection across the full Git history
- Dynamic testing of the running container with OWASP ZAP, with security headers verified by tests
- A hardened container that runs as a non-root user with a read-only filesystem
- Secrets injected at runtime only, never baked into the image
- A pipeline that fails closed: if any security check fails, the image is never pushed to the registry

## Architecture

```
Client → Flask app (Gunicorn) → Docker container → GitHub Container Registry
```

The app itself is intentionally simple — the point of this project is the pipeline, the security posture, and the observability around it, not the application logic.

## Deployment

A companion project, [terraform-ec2-demo](https://github.com/M-249S/terraform-ec2-demo), provisions a hardened AWS EC2 instance with Terraform and runs this exact image pulled from GitHub Container Registry. The full chain from code push to a live API on EC2 was verified end to end, then torn down with `terraform destroy`.

## Endpoints

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Welcome message |
| `/health` | GET | Liveness check, used by the Docker `HEALTHCHECK` |
| `/config-status` | GET | Confirms whether `API_KEY` is configured, without ever revealing its value |
| `/metrics` | GET | Prometheus metrics in text exposition format (excluded from its own counters) |
| `/items` | GET | List all items |
| `/items` | POST | Create an item — `{"name": "..."}`, returns 201 |
| `/items/<id>` | GET | Fetch a single item, 404 if it doesn't exist |
| `/items/<id>` | PUT | Update an item's name, 400 on invalid body |
| `/items/<id>` | DELETE | Delete an item, returns 204 |

`/items` is an in-memory CRUD resource — it demonstrates input validation and correct HTTP status codes (200/201/204/400/404), not persistent storage.

## Tech stack

- **App:** Python 3.12, Flask, Gunicorn
- **Container:** Docker, non-root user, read-only root filesystem
- **CI/CD:** GitHub Actions
- **SAST:** Bandit
- **Secret scanning:** Gitleaks
- **Vulnerability scanning:** Trivy (filesystem + image)
- **DAST:** OWASP ZAP (baseline scan)
- **Registry:** GitHub Container Registry (GHCR)
- **Testing:** pytest
- **Monitoring:** prometheus_client, Prometheus (via docker-compose)

## CI/CD pipeline

Every push to `main` runs seven stages. Later stages only run if earlier ones pass — a security failure anywhere stops the image from ever reaching the registry.

```
Lint ──▶ Test ──▶ ┌ SAST (Bandit)            ┐
                  ├ Secret Scan (Gitleaks)   ├──▶ DAST (ZAP) ──▶ Build → Scan → Push
                  └ Dependency Scan (Trivy)  ┘
```

| Stage | Tool | What it checks |
|---|---|---|
| Lint | flake8 | Code style (PEP 8) |
| Test | pytest | 33 unit tests covering all endpoints, CRUD validation, metrics, error handling, secret-safety, and security headers |
| SAST | Bandit | Insecure code patterns in the application source |
| Secret Scan | Gitleaks | Hardcoded credentials anywhere in the Git history |
| Dependency Scan | Trivy (filesystem) | Known CVEs in Python dependencies and OS packages |
| DAST | OWASP ZAP baseline | Starts the hardened container and checks its responses for missing security headers and other passive findings. Rules set to FAIL stop the pipeline. |
| Build & Push | Docker Buildx + Trivy (image) | Builds the image, scans the built image for CVEs, runs a smoke test with a read-only filesystem and an injected secret, and only then pushes to GHCR |

The pipeline is configured to `exit-code: 1` on any HIGH or CRITICAL Trivy finding — the build stage genuinely cannot succeed while a known, fixable vulnerability is present.

## Security decisions and trade-offs

A few choices worth calling out explicitly, since the reasoning matters more than the line of YAML:

- **Read-only root filesystem.** The container runs with `--read-only` and only `/tmp` mounted as writable (tmpfs). Gunicorn's worker heartbeat files are pointed at `/dev/shm` for the same reason. If the app were ever compromised, an attacker gets nowhere writing to disk.
- **Secrets are runtime-only.** `API_KEY` is injected via `-e` at container start, sourced from GitHub Secrets in CI. It is never present in a Docker layer, so it can't be extracted from the image itself — only from a running container with the right access.
- **Base image patched, not just pinned.** `apt-get upgrade` runs during the build to pull in OS-level CVE fixes (e.g. a HIGH-severity OpenSSL CVE found by Trivy during development, see commit history) that lag behind the upstream `python:3.12-slim` tag.
- **Security headers on every response.** The app sets `X-Content-Type-Options: nosniff`, a restrictive `Content-Security-Policy`, `X-Frame-Options`, `Cross-Origin-Resource-Policy`, `Permissions-Policy`, and `Cache-Control: no-store`. Tests assert them, and ZAP rules set to FAIL gate the pipeline.
- **The published image is the scanned image.** The image is built once, scanned with Trivy, smoke tested, and then pushed under its release tags. It is never rebuilt between the scan and the publish.
- **Least-privilege workflow token.** The token is read-only by default, and only the publish job is allowed to write packages. Checkouts do not keep credentials.
- **One gunicorn worker on purpose.** The items store and the Prometheus metrics live in process memory, so several workers would each hold their own copy and a created item could be missing on the next request. The container runs one worker with four threads, and a smoke test in CI fails if state is not shared across requests.
- **One ZAP rule is ignored on purpose.** Rule 10049 reports non-storable content as an informational alert. `no-store` makes responses non-storable intentionally.
- **The DAST stage was verified to fail closed.** A run where the ZAP stage failed skipped the build and push stage, so no image was published.
- **The ZAP baseline scan has limited reach.** It crawls links, and on this API it reached only the root path and `/sitemap.xml`. It is a baseline, not full API testing.
- **Every GitHub Action is pinned to a full commit SHA, not a tag or branch, and the OWASP ZAP image and the Docker base image are pinned by digest.** In March 2026, almost all version tags of `trivy-action` were force-pushed to malicious code (GHSA-69fq-xp46-6x23); only v0.35.0 stayed safe, and that is the commit this pipeline uses. Tags and branches can be moved, a commit SHA cannot. Dependabot opens pull requests to update the pins, and each one is reviewed before it is merged.
- **GHCR over Docker Hub.** No manually managed registry credentials — authentication uses the automatically scoped `GITHUB_TOKEN`, reducing the number of long-lived secrets in the project.

## Monitoring

The app exposes Prometheus-compatible metrics at `/metrics`, instrumented with the RED method — the same pattern used to monitor real production services:

- **Rate** — `http_requests_total`, labeled by method, endpoint, and status
- **Errors** — visible via the `status` label on the same counter
- **Duration** — `http_request_duration_seconds`, a histogram per endpoint

`/metrics` is excluded from its own counters, so scraping it doesn't create a feedback loop in the data.

A `docker-compose.yml` spins up the app alongside Prometheus, pre-configured to scrape it every 5 seconds:

```bash
docker compose up --build
```

- App: http://localhost:5000
- Metrics: http://localhost:5000/metrics
- Prometheus: http://localhost:9090 (check Status → Targets — the `devops-demo-app` job should show as UP)

```bash
docker compose down
```

The container keeps its security hardening (`read_only`, `tmpfs`) even in this local monitoring stack — observability doesn't come at the cost of the container's attack surface.

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

1. Copy `.env.example` to `.env` and fill in a local value — `.env` is git-ignored and never committed.
2. For CI, add the same key under **Settings → Secrets and variables → Actions → New repository secret** in GitHub. The pipeline reads it as `${{ secrets.API_KEY }}`.

## What I'd add next

- Switch the DAST stage to the ZAP API scan with an OpenAPI description, for deeper endpoint coverage
- A Grafana dashboard on top of the existing Prometheus metrics
- SBOM generation as a pipeline artifact

---

Built as part of a self-directed DevSecOps upskilling plan, applying a software engineering + IT security background to hands-on CI/CD practice.
