# 📚 Librarian — knowledge-rag

| Field | Value |
|---|---|
| Codename | Librarian |
| Code ID | `librarian` |
| Language | Python 3.11+ (FastAPI) |
| Port | 8001 |
| Vector DB | ChromaDB, **embedded** (no server to install) |
| Embeddings | all-MiniLM-L6-v2 (local, free) or `hash` (offline) |
| LLM | Claude Haiku writes the answer (optional: works without a key) |
| Called by | Conductor (skill `search_knowledge`) |
| Auth | `Bearer SERVICE_TOKEN` |

---

## What the Librarian does

Advisors constantly need answers buried in firm documents: *"What's our limit on a single stock?"*, *"When do RMDs start?"*, *"What did Research say about XYZ?"*. Today they search a shared drive, open PDFs and skim.

The Librarian answers those questions **from the firm's own documents only**, and **cites the exact passage** each fact came from, so the advisor can check it and compliance can audit it. If the documents don't contain the answer, it says so instead of guessing.

## What RAG is, in one picture

**RAG = Retrieval-Augmented Generation.** The LLM doesn't answer from memory. We first *retrieve* the relevant passages, then ask the LLM to *generate* an answer from those passages only.

```
 ONE-TIME (and whenever documents change): INGESTION
 ───────────────────────────────────────────────────
  rag\data\sample-docs\*.md
        │ load       front matter → title, doc_type, effective_date
        ▼
   ┌─────────┐ chunk      split by heading, ~700 chars, 120 overlap
   │ Chunks  │ safety     quarantine chunks that contain instructions to the AI
   └────┬────┘ embed      text → 384 numbers (MiniLM)
        ▼
   ┌──────────────────────────┐
   │ ChromaDB  (rag\chroma-store) │  id · vector · text · metadata
   └──────────────────────────┘

 EVERY QUESTION: RETRIEVE + GENERATE
 ───────────────────────────────────
  "When do RMDs start?"
        │ embed the question
        ▼
   nearest vectors in Chroma (cosine similarity)
        │ drop weak matches (< 0.30), one passage per section, top 4
        ▼
   Claude: "answer ONLY from these numbered passages, cite [n]"
        │ code keeps only citations that really exist
        ▼
   { answer: "...age 73, rising to 75 in 2033 [1]",
     citations: [ {ref 1, title "RMD Advisor Summary", section "Who must take RMDs", score 0.71} ],
     grounded: true }
```

## Your questions answered

**Do we need a vector database?** Yes. That's where the embeddings live and how we find "nearest meaning" fast.

**ChromaDB or Pinecone?** **ChromaDB**, running *embedded*: it's a Python library (`pip install chromadb`) that saves to a folder. Nothing to install, no account, no cost. Pinecone is a paid cloud service. It's a good choice at scale, but the code is nearly identical (add vectors, query vectors), so you can swap later. In production you'd typically run Chroma as a server or use a managed service.

**Do I install anything?** No, only the `pip install -r requirements.txt` you'd do anyway. On the **first start**, Chroma downloads the embedding model (all-MiniLM-L6-v2, about 80 MB) and caches it in your user folder. After that it works offline.

**Where's the data?** Documents: `aurelius\rag\data\sample-docs\`. Index: `aurelius\rag\chroma-store\` (git-ignored, rebuilt any time with `python scripts\ingest.py`).

## Folder map

```
knowledge-rag/
├── src/
│   ├── main.py              ▶ ENTRY POINT: python src\main.py  (port 8001)
│   ├── rag/                 ★ the RAG pipeline, read in this order
│   │   ├── loader.py          1 load files + front matter
│   │   ├── chunker.py         2 split into passages
│   │   ├── safety.py          3 quarantine poisoned passages
│   │   ├── embeddings.py      4 text → vectors (minilm | hash)
│   │   ├── store.py           5 ChromaDB: save + search
│   │   ├── ingest.py          ties 1-5 together
│   │   └── retriever.py       6 question → best passages
│   ├── llm/answerer.py      7 Claude writes the cited answer (or extractive fallback)
│   ├── api/app.py           endpoints
│   ├── security/auth.py     service-token check
│   ├── schemas/models.py    contract + SearchInput / SearchResult
│   └── core/                settings, logging
├── scripts/ingest.py        rebuild the index from the command line
├── tests/                   29 tests (offline, no API key)
├── api-tests.http           every request to try
└── TESTING.md               start & test runbook

aurelius/rag/
├── data/sample-docs/        8 sample documents (7 real + 1 poisoned)
└── chroma-store/            the vector index (created at runtime)
```

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | none | Alive + chunks indexed + embedding model |
| GET | `/.well-known/agent.json` | none | Agent card + JSON schemas |
| POST | `/invoke` | service | `search_knowledge`: the agent contract |
| POST | `/v1/search` | service | **Raw retrieval, no LLM**: see passages and scores |
| GET | `/v1/documents` | service | What's indexed + what was quarantined |
| POST | `/v1/ingest` | service | Re-read the docs folder and rebuild |

### `search_knowledge` input
```json
{ "query": "When do RMDs start?", "top_k": 4, "doc_type": "guide" }
```
`top_k` (1–10) and `doc_type` (`policy`, `guide`, `research`, `product`, `external`) are optional.

### Output
```json
{
  "answer": "From the firm's documents:\n- ... RMD age is 73, rising to 75 in 2033. [1]",
  "grounded": true,
  "citations": [{ "ref": 1, "title": "Required Minimum Distributions (RMDs) - Advisor Summary",
                  "source": "rmd-guide.md", "section": "Who must take RMDs",
                  "effective_date": "2026-02-01", "score": 0.71, "snippet": "..." }],
  "passages_considered": 4,
  "answered_by": "claude-haiku-4-5-20251001"
}
```

## The sample documents

| File | Type | Teaches |
|---|---|---|
| `concentration-policy.md` | policy | 10% single-stock limit, escalation at 15% |
| `rebalancing-policy.md` | policy | Rebalance at 5-point drift |
| `client-communications-policy.md` | policy | No promissory language, required disclosure (same rules Sentinel enforces) |
| `tax-loss-harvesting.md` | guide | Wash-sale rule (30 days before/after) |
| `rmd-guide.md` | guide | RMD age 73 → 75 in 2033 |
| `equity-research-xyz.md` | research | XYZ Corp downgraded to Hold (ties to the Patel demo) |
| `intl-bond-fund-factsheet.md` | product | Fictional fund facts |
| `vendor-market-note.md` | external | ⚠️ **Poisoned** with hidden instructions: watch it get quarantined |

All are fictional training material for this project. The tax and RMD summaries reflect general US rules but say "verify current IRS guidance": real documents must be kept current.

## Security principles in this agent

1. **Grounding**: answers only from retrieved passages; "not found" instead of guessing.
2. **Citation validation**: code removes any `[n]` the model invents.
3. **Indirect prompt-injection defense**: poisoned passages are quarantined at ingest, and retrieved text is wrapped in `<document>` tags as untrusted data.
4. **Relevance cut-off**: weak matches are dropped before the LLM sees them.
5. **Least privilege**: service-token only; humans reach it through the Conductor (and Sentinel).
6. **Traceability**: every citation carries document, section and effective date.
7. **Cost control**: small model, short prompts, prompt caching, top 4 passages only.

**Next step in a real firm:** document-level permissions (`access_level` metadata, filtered by the advisor's role), so the Librarian only retrieves what that user may read.
