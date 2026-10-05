# Testing Atrium (web), step by step

Run every command in **PowerShell** (not Command Prompt).

## 0. One-time laptop setup

You already have Node.js from the Herald and Liaison agents. Check it:

```powershell
node -v     # must be v22.12 or newer
npm -v
```

## 1. Install the app's libraries (once)

They go into `frontend\web\node_modules`, inside the project, like the other agents.

```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\frontend\web
npm ci
```

`npm ci` installs exactly the versions in `package-lock.json`.

## 2. Run the tests (no servers needed)

```powershell
npm test
npm run typecheck
```

EXPECT: `Tests 19 passed (19)` and no TypeScript errors.

The tests use a fake Conductor that answers with **real recorded agent outputs**, so they cover sign-in, the dossier, a failed agent, an unknown household, and approving or refusing an email.

## 3. Prepare the Conductor

The `conductor_apps` update must be in `agents\python\orchestrator`, and `aurelius\.env` must have these two lines:

```
JWT_SIGNING_KEY=<the long random value you already set>
DEV_LOGIN_PASSWORD=<choose one, 12+ characters>
```

## 4. Quick start: the Conductor alone (recorded answers)

**Terminal 1:**

```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\agents\python\orchestrator
.\run.ps1
```

With `MOCK_AGENTS=true` (the default), the Conductor answers from recorded agent outputs, so you don't need the other 9 agents yet.

**Terminal 2:**

```powershell
cd C:\Users\ajith\OneDrive\Documents\1_Projects\aurelius\frontend\web
npm run dev
```

Open http://127.0.0.1:5173.

## 5. What to try

| # | Do this | Expect |
|---|---|---|
| 1 | Sign in with any username and a **wrong** password | "That username and password don't match." The password field is cleared. |
| 2 | Sign in with your DEV_LOGIN_PASSWORD | "Good to see you, …" and 3 households on the left |
| 3 | Click **Patel** | Header shows $2.35M. The agent strip shows 6 agents with their timings. Needs you lists Paperwork (Raj's ID), 2 Overdue tasks, Market (XYZ), Rebalance and Concentration. |
| 4 | Retirement: click **64** | The odds rerun for up to 3 ages. With recorded answers the numbers stay the same; with the real Actuary they change. |
| 5 | Click **Show how a market crash would hit this portfolio** | Table with 2008, COVID, dot-com, 2022 rates and single stock halved |
| 6 | Write to them: click **Draft email** | A draft with `[Add your key points]`. **Approve is disabled** until you replace the placeholder. |
| 7 | Replace the body with `This fund offers guaranteed returns of 8%.` and approve | Refused: "The security check changed the text". The body now shows `[removed: non-compliant claim]`. |
| 8 | Write a clean body and approve | "Approved and logged to the CRM as note N-…". Aurelius never sends email. |
| 9 | Ask Aurelius: click the policy suggestion | Answer from the Librarian with sources and a disclosure. "Planned by the fallback rules" means no LLM key was used. |
| 10 | Go to http://127.0.0.1:5173/clients/nobody-1 | "There's no household with the id nobody-1." |
| 11 | Stop the Conductor (Ctrl+C), then click another household | A clear error naming the Conductor. The rail news shows "Offline, retrying" and reconnects when you restart it. |
| 12 | Make the window narrow (phone width) | Households become a row of tabs, sections stack, and nothing scrolls sideways. |

## 6. Full swarm: real agents and live news

Start the agents you want to be real (MCP, Liaison, Pulse, and so on, as in each agent's TESTING.md). Then list them in `aurelius\.env`:

```
REAL_AGENTS=sentinel,librarian,analyst,scribe,herald,liaison,pulse,notary,actuary
```

Restart the Conductor and refresh Atrium. The rail says **Listening to Pulse**, and now it really is relaying from Pulse.

Now push a news item into Pulse from a third PowerShell window:

```powershell
$h = @{ Authorization = "Bearer $env:SERVICE_TOKEN"; "Content-Type" = "application/json" }
$b = '{"event_id":"EV-7101","date":"2026-10-03","type":"company_news","severity":"high","headline":"XYZ Corp names a new CFO after guidance cut","summary":"Interim CFO steps in.","source":"demo","symbols":["XYZ"],"price_change_pct":-3}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8301/v1/events -Headers $h -Body $b
```

(If `$env:SERVICE_TOKEN` is empty, paste the value from your `.env` in its place, but only in your own terminal.)

EXPECT: within a second, the headline appears under **Market news** in the browser, without a refresh. That is Go → Python → browser.

## 7. Production build

```powershell
npm run build
npm run preview      # http://127.0.0.1:4173, with the strict CSP turned on
```

In the browser's DevTools (F12 → Console) there should be no CSP errors.

## Troubleshooting

| You see | Fix |
|---|---|
| "Sign-in is turned off" | Add DEV_LOGIN_PASSWORD to `aurelius\.env` and restart the Conductor. |
| "The Conductor isn't reachable" | Start it (step 4). Check http://127.0.0.1:8000/health. |
| "Too many attempts" | 5 wrong passwords in 5 minutes. Wait, or restart the Conductor. |
| Port 5173 already in use | Another `npm run dev` is still running. Close it. |
| "Listening to Pulse" but no news ever arrives | Normal with recorded answers: the Conductor keeps the stream open but has nothing to relay. Run Pulse and list it in REAL_AGENTS (step 6). |
