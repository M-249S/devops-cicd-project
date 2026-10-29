# Security

This project is a small Flask API used to practice DevSecOps. This document explains which security controls exist, how the CI/CD pipeline enforces them, and what is deliberately not covered.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use GitHub's private vulnerability reporting for this repository (Security tab, "Report a vulnerability"), or email mujahid249m@gmail.com. This is a learning project with no production users, so there is no formal response time, but reports are welcome.

## How the pipeline enforces security

Every push to `main` runs seven jobs. The image is published to GitHub Container Registry only if all of them pass.

| Stage | Tool | What it checks |
|---|---|---|
| Lint | flake8 | Code style |
| Test | pytest | Endpoints, input validation, metrics, secret safety, and security headers |
| SAST | Bandit | Insecure patterns in the application source |
| Secret scan | Gitleaks | Hardcoded credentials in the full Git history |
| Dependency scan | Trivy (filesystem) | Known CVEs in dependencies, HIGH and CRITICAL fail the build |
| DAST | OWASP ZAP baseline | The running, hardened container: security headers and passive checks |
| Build and push | Docker Buildx, Trivy (image) | Image CVEs, a smoke test of runtime secret injection, then publish |

The pipeline fails closed. A failing ZAP rule or a HIGH or CRITICAL Trivy finding stops the publish step. This was verified with a real failed run, where the DAST stage failed and the build and push stage was skipped.

## Mapping to the OWASP Top 10:2025

The OWASP Top 10:2025 was released in November 2025. It is an awareness document, not a test checklist, so this table states honestly what this project does and does not address. Category names were checked against the published 2025 list.

| Category | Status | What exists | Gaps |
|---|---|---|---|
| A01 Broken Access Control | Not applicable | The API has no users, no authentication, and stores only demo data in memory. The API makes no outbound requests, so server-side request forgery (now part of A01) does not apply. | Any real use would need authentication and authorization. |
| A02 Security Misconfiguration | Partly covered | Container runs as non-root with a read-only root filesystem and a tmpfs for `/tmp`. Debug mode is off by default. Security headers are set on every response and verified by pytest and by ZAP rules set to FAIL. The companion Terraform project requires IMDSv2, encrypts the root volume, and runs a Trivy IaC scan. | The service speaks plain HTTP. The companion Terraform project defaults SSH to `0.0.0.0/0`. |
| A03 Software Supply Chain Failures | Partly covered | Trivy scans dependencies and the built image. Gitleaks scans history. Publishing uses the scoped `GITHUB_TOKEN`, not a stored registry password. | `trivy-action` is pinned to `@master`. GitHub Actions are pinned by tag, not commit SHA. The base image is not pinned by digest. No SBOM is generated. |
| A04 Cryptographic Failures | Partly covered | The only secret, `API_KEY`, is injected at runtime and never baked into an image layer. `/config-status` reports whether it is set without revealing it, and a test checks that it never leaks. | No TLS in this project, and no sensitive data is stored. |
| A05 Injection | Partly covered | `/items` validates that `name` is a non-empty string and returns 400 otherwise. There is no database, no shell call, and no HTML rendering. Bandit scans the source. | Validation is basic, with no length limits. |
| A06 Insecure Design | Not covered | The scope is intentionally small and the pipeline is designed to fail closed. | There is no threat model and no rate limiting. |
| A10 Mishandling of Exceptional Conditions | Partly covered | Custom handlers return generic JSON for 404 and 500, so no stack traces are exposed. Tests cover 404 and invalid request bodies. | Other HTTP errors, such as 405, use Flask's default HTML error page. |

Categories A07, A08, and A09 have not been assessed in this project.

## Known limitations

- The ZAP baseline scan only crawls links it can reach. On this API it reached the root path and `/sitemap.xml`, not the `/items`, `/config-status`, or `/metrics` routes. It is a baseline, not full API testing. Deeper coverage would need an OpenAPI description and the ZAP API scan.
- One ZAP rule (10049, Non-Storable Content) is set to IGNORE. The `Cache-Control: no-store` header makes responses non-storable on purpose, and ZAP reports that as an informational alert.
- The scans catch known issues and common misconfigurations. They are not a substitute for a manual security review.

## What I would improve next

- Pin `trivy-action`, other actions, and the base image to commit SHAs or digests, and add Dependabot.
- Generate an SBOM as a pipeline artifact.
- Add an OpenAPI description and switch the DAST stage to the ZAP API scan.
- Add custom JSON handlers for all HTTP errors.
- Add rate limiting and request size limits.
