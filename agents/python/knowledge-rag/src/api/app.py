"""
Librarian HTTP API.

Endpoints
  GET  /health                  liveness + how many passages are indexed (no auth)
  GET  /.well-known/agent.json  agent card with input/output schemas (no auth)
  POST /invoke                  agent contract: search_knowledge (service token)
  POST /v1/search               raw retrieval, NO LLM: see passages and scores (service token)
  GET  /v1/documents            what's in the index (service token)
  POST /v1/ingest               re-read the docs folder and rebuild the index (service token)

Started by src/main.py.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from core.config import VERSION, Settings, get_settings
from llm.answerer import Answerer
from rag.embeddings import Embedder, build_embedder
from rag.ingest import run_ingest
from rag.retriever import Retriever
from rag.store import VectorStore
from schemas.models import AgentRequest, AgentResponse, IngestReport, SearchInput, SearchResult
from security.auth import check_startup_security, require_service

log = logging.getLogger("librarian.api")

SKILL_DESC = ("Answer a question from firm research, product documents and policies, "
              "with citations to the exact source passages.")


class RawSearch(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=10)
    doc_type: str | None = None


def create_app(settings: Settings | None = None, embedder: Embedder | None = None) -> FastAPI:
    settings = settings or get_settings()
    check_startup_security(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        emb = embedder or build_embedder(settings.embedding_provider)
        store = VectorStore(settings.chroma_dir, settings.collection_name)
        app.state.embedder = emb
        app.state.store = store
        app.state.retriever = Retriever(store, emb, settings.effective_min_score)
        app.state.answerer = Answerer(settings)
        app.state.ingest_lock = asyncio.Lock()
        app.state.last_ingest = None
        if settings.auto_ingest and store.count() == 0:
            log.info("index empty: ingesting %s (first run may download the embedding model)",
                     settings.docs_dir)
            app.state.last_ingest = await asyncio.to_thread(run_ingest, settings, store, emb)
        log.info("librarian_started port=%s embeddings=%s chunks=%d llm=%s",
                 settings.port, emb.name, store.count(), settings.use_llm)
        yield

    app = FastAPI(title="Aurelius Librarian (knowledge-rag)", version=VERSION, lifespan=lifespan)
    app.state.settings = settings

    @app.middleware("http")
    async def headers(request: Request, call_next):
        request.state.trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Trace-Id"] = request.state.trace_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        trace = getattr(request.state, "trace_id", "unknown")
        log.exception("unhandled_error trace=%s", trace)
        return JSONResponse(status_code=500, content={"detail": "Internal error", "trace_id": trace})

    # ------------------------------------------------------------------ routes
    @app.get("/health")
    async def health(request: Request):
        return {"status": "ok", "agent": "librarian", "version": VERSION,
                "chunks_indexed": request.app.state.store.count(),
                "embeddings": request.app.state.embedder.name}

    @app.get("/.well-known/agent.json")
    async def agent_card():
        return {
            "name": "librarian", "codename": "Librarian", "folder": "knowledge-rag",
            "language": "Python", "version": VERSION,
            "description": "Retrieval-augmented answers from firm documents, with citations.",
            "auth": "Bearer SERVICE_TOKEN",
            "endpoints": {"invoke": "/invoke", "search": "/v1/search",
                          "documents": "/v1/documents", "ingest": "/v1/ingest"},
            "skills": {"search_knowledge": {
                "description": SKILL_DESC,
                "input_schema": SearchInput.model_json_schema(),
                "output_schema": SearchResult.model_json_schema()}},
        }

    @app.post("/invoke", response_model=AgentResponse)
    async def invoke(body: AgentRequest, request: Request, _: str = Depends(require_service)):
        start = time.perf_counter()
        if body.skill != "search_knowledge":
            return AgentResponse(agent="librarian", status="error", error=f"unknown skill {body.skill}")
        try:
            # the Conductor may add extra keys (client_id, prior_results): ignore them
            params = SearchInput.model_validate(
                {k: v for k, v in body.input.items() if k in SearchInput.model_fields})
        except ValidationError as exc:
            return AgentResponse(agent="librarian", status="error",
                                 error=f"invalid input: {exc.errors()[0]['loc'][0]} {exc.errors()[0]['msg']}")
        if len(params.query) > settings.max_query_chars:
            return AgentResponse(agent="librarian", status="error",
                                 error=f"query longer than {settings.max_query_chars} characters")

        state = request.app.state
        hits = await asyncio.to_thread(state.retriever.retrieve, params.query,
                                       params.top_k or settings.top_k, params.doc_type)
        result = await state.answerer.answer(params.query, hits)
        log.info("search trace=%s passages=%d grounded=%s best=%.3f answered_by=%s ms=%d",
                 body.context.trace_id, len(hits), result.grounded,
                 hits[0].score if hits else 0.0, result.answered_by,
                 int((time.perf_counter() - start) * 1000))
        return AgentResponse(agent="librarian", status="ok", output=result.model_dump())

    @app.post("/v1/search")
    async def raw_search(body: RawSearch, request: Request, _: str = Depends(require_service)):
        state = request.app.state
        vector = (await asyncio.to_thread(state.embedder.embed, [body.query]))[0]
        hits = await asyncio.to_thread(state.store.search, vector, body.top_k, body.doc_type)
        cutoff = settings.effective_min_score
        return {
            "query": body.query, "min_score": cutoff,
            "results": [{"score": h.score, "passes_cutoff": h.score >= cutoff,
                         "title": h.metadata["title"], "section": h.metadata["section"],
                         "source": h.metadata["source"], "text": h.text} for h in hits],
        }

    @app.get("/v1/documents")
    async def documents(request: Request, _: str = Depends(require_service)):
        state = request.app.state
        last: IngestReport | None = state.last_ingest
        return {"collection": settings.collection_name, "docs_dir": str(settings.docs_dir),
                "chunks_indexed": state.store.count(),
                "documents": await asyncio.to_thread(state.store.sources),
                "quarantined_last_ingest": last.quarantined if last else "run POST /v1/ingest to see"}

    @app.post("/v1/ingest", response_model=IngestReport)
    async def ingest(request: Request, _: str = Depends(require_service)):
        state = request.app.state
        async with state.ingest_lock:  # one rebuild at a time
            report = await asyncio.to_thread(run_ingest, settings, state.store, state.embedder)
        state.last_ingest = report
        return report

    return app
