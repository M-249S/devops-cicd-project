# Pinned by digest. Dependabot proposes a new digest when the tag moves.
FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS base

# Prevent Python from writing .pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Apply latest OS security patches (base image packages can lag behind
# upstream CVE fixes between image builds)
RUN apt-get update && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user and switch to it
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# One worker process on purpose: the items store and the Prometheus metrics
# live in process memory, so several workers would each hold their own copy
# (an item created through one worker would be missing on the other).
# Threads give concurrency without splitting that state.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--worker-tmp-dir", "/dev/shm", "app:app"]
