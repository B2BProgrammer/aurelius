# Atrium (web)

The advisor's workstation for Aurelius, built with React 19, TypeScript and Vite.

Atrium talks to **one** service, the Conductor (`agents/python/orchestrator`, port 8000). It never calls an agent directly. The Conductor asks the agents, checks their answers with Sentinel, and hands back what the screen needs.

```
Browser (localhost:5173)
   │  /v1/...  (same origin; Vite forwards it)
   ▼
Conductor :8000 ──► Liaison, Analyst, Notary, Actuary, Pulse, Scribe, Herald, Librarian, Sentinel
```

## What's on the screen

| Part | Comes from | Conductor endpoint |
|---|---|---|
| Sign in | Conductor (dev password, then a JWT) | `POST /v1/auth/login` |
| Households on the left | Liaison (CRM) | `GET /v1/clients` |
| The dossier: header, agent strip, Needs you, Portfolio, Market, Meetings | 6 agents **in parallel** | `GET /v1/clients/{id}/overview` |
| Retirement what-if (ages, spending) and stress test | Actuary (Java) | `POST /v1/skills/actuary/...` |
| Write to them: draft, edit, approve | Herald, then Sentinel, then Liaison logs a CRM note | `POST /v1/skills/herald/draft_email`, `POST /v1/drafts/approve` |
| Ask Aurelius | Conductor plans and runs the agents | `POST /v1/chat` |
| Market news (live) | Pulse (Go), relayed by the Conductor | `GET /v1/stream` (Server-Sent Events) |

## Project layout

```
frontend/web/
├─ index.html              page shell (no-referrer policy)
├─ vite.config.ts          dev server, /v1 proxy, CSP for builds, test setup
├─ src/
│  ├─ main.tsx             starts React: Query cache, sign-in, router, fonts
│  ├─ App.tsx              routes: sign-in, or the workspace
│  ├─ api/
│  │  ├─ client.ts         the ONLY fetch(): token, 401 sign-out, trace IDs
│  │  ├─ types.ts          what the Conductor returns
│  │  ├─ hooks.ts          TanStack Query hooks, one per need
│  │  └─ stream.ts         live news over SSE, with reconnect
│  ├─ lib/
│  │  ├─ auth.tsx          session (sessionStorage), expiry timer
│  │  └─ format.ts         money, dates, "over 99%"
│  ├─ pages/               SignIn, Workspace (rail), Dossier
│  ├─ components/          one file per dossier section
│  └─ styles/app.css       the whole design: tokens, layout, dark mode
└─ tests/                  vitest + Testing Library, fixtures from real agent outputs
```

## Security choices (good interview talking points)

- **One door.** The browser only knows the Conductor. Agent URLs and the SERVICE_TOKEN never reach the browser.
- **No cross-origin calls in dev.** Vite proxies `/v1` to the Conductor, so the page and the API share one origin.
- **Token handling.** The JWT is kept in memory and in `sessionStorage`, which is cleared when the tab closes, and never in `localStorage`. The app signs out when the token expires or on any 401. For production, the stronger option is an httpOnly cookie, which page scripts can't read at all.
- **Live news without leaking the token.** `EventSource` can't send headers, and a token in the URL ends up in logs, so `stream.ts` reads SSE with `fetch()` and an `Authorization` header.
- **Strict CSP in builds.** Scripts, styles, fonts and API calls come only from the app's own origin. The fonts are bundled, so nothing loads from Google.
- **No HTML injection.** Answers are rendered with `react-markdown`, which ignores raw HTML.
- **Human in the loop.** Nothing goes to a client automatically. Approval re-runs Sentinel. If Sentinel changes the text, you must review it again. The app won't approve while `[placeholders]` remain. Aurelius never sends email; the approval only logs a CRM note.
- **Traceable errors.** Every error shows the `X-Trace-Id`, so you can find the same request in every agent's log.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | dev server on http://127.0.0.1:5173 |
| `npm test` | the tests (no Conductor needed) |
| `npm run typecheck` | TypeScript strict check |
| `npm run build` | production build into `dist/` |
| `npm run preview` | serves `dist/` on http://127.0.0.1:4173 |

The Conductor URL defaults to `http://127.0.0.1:8000`. To change it, create `frontend/web/.env.local` with `CONDUCTOR_URL=http://...`.

See **TESTING.md** for the step-by-step run.
