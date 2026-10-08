# Librarian (knowledge-rag) container image.
#
# UNLIKE the other agents, this image is built from the REPO ROOT, because the
# policy documents live outside this folder (rag/data/sample-docs).
#
# Build (from the aurelius folder):
#   docker build -f agents/python/knowledge-rag/Dockerfile -t aurelius/librarian:local .
# Run:
#   docker run --rm -p 8001:8001 --env-file .env aurelius/librarian:local
#
# The file Dockerfile.dockerignore (next to this one) limits what is sent from
# the repo root to just the three folders below.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/app \
    DOCS_DIR=/app/docs \
    CHROMA_DIR=/app/chroma-store

WORKDIR /app

# 1. Packages (chromadb is large: this layer is cached until requirements.txt changes)
COPY agents/python/knowledge-rag/requirements.txt .
RUN pip install -r requirements.txt

# 2. Normal user, then download the embedding model ONCE, at build time.
#    The container then starts without internet access, and every replica is identical.
RUN useradd --uid 10001 --create-home app && mkdir -p /app/chroma-store && chown -R 10001:10001 /app
USER 10001
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction as F; F()(['warm up'])"

# 3. Code and the documents to index. The index itself is built at startup
#    (auto-ingest) into /app/chroma-store.
COPY --chown=10001:10001 agents/python/knowledge-rag/src ./src
COPY --chown=10001:10001 rag/data/sample-docs ./docs

EXPOSE 8001
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=4)"

CMD ["uvicorn", "main:build_app", "--factory", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8001"]
