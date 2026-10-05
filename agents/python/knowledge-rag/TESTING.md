# Librarian: Start & Test Runbook

## 1. First-time setup (once)

```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\python\knowledge-rag
py -m venv .venv
.\.venv\Scripts\Activate.ps1                 # prompt now starts with (.venv)
python -m pip install --upgrade pip
pip install -r requirements.txt              # includes chromadb (inside .venv only)
python -c "import chromadb; print('ChromaDB', chromadb.__version__)"
python -m pytest -v                          # expect: 29 passed (offline, no key needed)
```

Needs `SERVICE_TOKEN` in `aurelius\.env` (the same one the Conductor and Sentinel use).

## 2. Build the index (optional: the server also does this on first start)

```powershell
python scripts\ingest.py
```
✅ The first run downloads the embedding model (~80 MB, once).
✅ It ends with a JSON report: `"documents": 8`, `"chunks": ~27`, and `vendor-market-note.md` under `"quarantined"`.

Look at what was created: `aurelius\rag\chroma-store\` now holds the vector index.

## 3. Start the Librarian

```powershell
python src\main.py
```
✅ `librarian_started port=8001 embeddings=minilm chunks=27`
Swagger: **http://localhost:8001/docs** (Authorize with the SERVICE_TOKEN)

## 4. Fire the requests

Get the token: `Select-String -Path ..\..\..\.env -Pattern '^SERVICE_TOKEN='`

**Option A: VS Code.** Open **`api-tests.http`**, paste the token into `@serviceToken`, click **Send Request**.

**Option B: Browser.** http://localhost:8001/docs → Authorize → try `/v1/search` first: it shows the raw passages and scores.

**Option C: PowerShell** (Terminal 2):
```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\python\knowledge-rag
$svc = ((Get-Content ..\..\..\.env | Where-Object { $_ -match '^SERVICE_TOKEN=' }) -split '=', 2)[1] -replace '\s+#.*$', ''
$h = @{ Authorization = "Bearer $svc" }

function Ask($q) {
    $body = @{ skill = "search_knowledge"; input = @{ query = $q }
               context = @{ trace_id = "ps-test"; user_id = "dev-advisor" } } | ConvertTo-Json -Depth 5
    $r = Invoke-RestMethod http://localhost:8001/invoke -Method Post -Headers $h -ContentType "application/json" -Body $body
    $r.output.answer
    $r.output.citations | Format-Table ref, source, section, score
}

function Peek($q) {   # raw retrieval: passages + scores, no LLM
    $body = @{ query = $q; top_k = 5 } | ConvertTo-Json
    (Invoke-RestMethod http://localhost:8001/v1/search -Method Post -Headers $h -ContentType "application/json" -Body $body).results |
        Format-Table score, passes_cutoff, source, section
}

Ask  "What is the firm policy on single stock concentration?"
Ask  "When do clients have to start required minimum distributions?"
Ask  "At what age must retirees begin pulling money out of their traditional IRA?"   # semantic match
Ask  "Best pizza in Chicago"                                                         # not found
Peek "When should I rebalance a portfolio?"
Peek "Best pizza in Chicago"                                                         # nothing passes
(Invoke-RestMethod http://localhost:8001/v1/documents -Headers $h).quarantined_last_ingest
```

## 5. Run with the Conductor (and Sentinel)

**a)** In `aurelius\.env`: `REAL_AGENTS=sentinel,librarian`
**b)** Three terminals, each: `cd` into the agent folder → `.\.venv\Scripts\Activate.ps1` → `python src\main.py`

| Terminal | Folder | Port |
|---|---|---|
| 1 | `compliance-guard` | 8004 |
| 2 | `knowledge-rag` | 8001 |
| 3 | `orchestrator` | 8000 |

**c)** Use the Conductor's `api-tests.http` (or Swagger on 8000):

| Check | Expect |
|---|---|
| `GET /v1/agents` | `sentinel: up`, `librarian: up`, others `mock` |
| 4.4 "What is the firm policy on single stock concentration?" | Briefing quotes the policy with **Sources: [1] Single-Stock Concentration Policy › ...**, then Sentinel's disclosure |
| Terminal 2 | `search trace=... passages=4 grounded=True` |

## 6. Experiments worth doing

| Try | What you learn |
|---|---|
| Add your own `.md` file to `aurelius\rag\data\sample-docs`, run `python scripts\ingest.py`, ask about it | The full ingest → retrieve loop |
| Delete a file, re-ingest | `removed_sources` shows it's gone from the index |
| Set `EMBEDDING_PROVIDER=hash`, restart, run request 3.6 | Keyword matching vs. semantic matching |
| Set `MIN_SCORE=0.6`, restart | Too strict: real questions start returning "not found" |
| Add `ANTHROPIC_API_KEY`, restart | Extractive quotes become a written answer by Claude, same citations |

## Scorecard (`api-tests.http`)

| # | Test | Expect |
|---|---|---|
| 1.1 / 1.2 | health / agent card | 200 |
| 2.1 | no token | 401 |
| 2.2 | documents | 7 docs + vendor note quarantined |
| 3.1–3.5 | policy, RMD, wash sale, XYZ rating, fund | right document cited |
| 3.6 | semantic question | rmd-guide.md (minilm) |
| 3.7 | doc_type=policy | only policies |
| 3.8 | pizza | grounded=false, no citations |
| 3.9 | Conductor extras | ok |
| 4.1 / 4.2 | raw search | scores; pizza fails cutoff |
| 5.1 | poisoned topic | no injected text in the answer |
| 5.2 | re-ingest | report |
| 6.1–6.4 | bad input | status "error" |
| 6.5 | missing context | 422 |

## Troubleshooting

| You see | Fix |
|---|---|
| Long pause on first start | It's downloading the embedding model (~80 MB, once) |
| Model download fails (firewall / proxy) | Set `EMBEDDING_PROVIDER=hash` in `aurelius\.env` to work offline |
| `chunks_indexed: 0` | Docs folder empty or wrong: check `aurelius\rag\data\sample-docs`, then `POST /v1/ingest` |
| Every answer is "couldn't find this" | `MIN_SCORE` too high, or you switched provider: run `python scripts\ingest.py` |
| `SERVICE_TOKEN is missing or too short` | Same fix as Sentinel: 24+ character token in `aurelius\.env` |
| Conductor shows `librarian: down` | Librarian not running on 8001, or `REAL_AGENTS` misspelled |
| Want a clean start | Stop the server, delete everything inside `aurelius\rag\chroma-store` except `.gitkeep`, start again |
