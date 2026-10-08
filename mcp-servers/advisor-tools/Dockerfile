# advisor-tools MCP server (advisor-tools) container image.
#
# Build (from this folder):   docker build -t aurelius/advisor-tools:local .
# Run:                        docker run --rm -p 8500:8500 --env-file ..\..\.env aurelius/advisor-tools:local
#
# LEARN: the order of the steps matters. Docker caches each step, so we copy
# requirements.txt and install packages BEFORE copying the code. Changing code
# then rebuilds in seconds; only a change to requirements.txt reinstalls packages.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 1. Packages (cached until requirements.txt changes)
COPY requirements.txt .
RUN pip install -r requirements.txt

# 2. Code and data
COPY src ./src
COPY data ./data

# 3. Run as a normal user, never root. A numeric id lets Kubernetes verify runAsNonRoot.
RUN useradd --uid 10001 --create-home app && mkdir -p logs && chown -R 10001:10001 /app
USER 10001

ENV HOST=0.0.0.0

EXPOSE 8500
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8500/health', timeout=4)"

# main.py reads HOST and MCP_PORT; HOST=0.0.0.0 (set above) makes it reachable from other containers.
CMD ["python", "src/main.py"]
