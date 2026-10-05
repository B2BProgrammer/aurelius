Here's your start-up list, one terminal per step and in this order. Each block is the same pattern: go to the folder, start it, check it.

Before you start (once): in C:\work\1_Projects\aurelius\.env, make sure you have:

MOCK_AGENTS=false
DEV_LOGIN_PASSWORD=<your password>
Aurelius start-up order

For each step: open a new PowerShell terminal, paste the block and leave it running.

1. MCP server: port 8500
powershell
cd C:\work\1_Projects\aurelius\mcp-servers\advisor-tools
.\.venv\Scripts\Activate.ps1
python src\main.py

Check: http://127.0.0.1:8500/health

2. Sentinel (security): port 8004
powershell
cd C:\work\1_Projects\aurelius\agents\python\compliance-guard
.\.venv\Scripts\Activate.ps1
python src\main.py

Check: http://127.0.0.1:8004/health

3. Liaison (CRM): port 8102
powershell
cd C:\work\1_Projects\aurelius\agents\node\crm-sync
npm run dev

Check: http://127.0.0.1:8102/health

4. Librarian (documents): port 8001
powershell
cd C:\work\1_Projects\aurelius\agents\python\knowledge-rag
.\.venv\Scripts\Activate.ps1
python scripts\ingest.py
python src\main.py

ingest.py loads the firm's documents. It's only needed the first time, or after you add documents. Running it again is harmless.
Check: http://127.0.0.1:8001/health

5. Analyst (portfolio): port 8002
powershell
cd C:\work\1_Projects\aurelius\agents\python\portfolio-insights
.\.venv\Scripts\Activate.ps1
python src\main.py

Check: http://127.0.0.1:8002/health

6. Scribe (meetings): port 8003
powershell
cd C:\work\1_Projects\aurelius\agents\python\meeting-intel
.\.venv\Scripts\Activate.ps1
python src\main.py

Check: http://127.0.0.1:8003/health

7. Herald (emails): port 8101
powershell
cd C:\work\1_Projects\aurelius\agents\node\client-comms
npm run dev

Check: http://127.0.0.1:8101/health

8. Notary (KYC, Java): port 8201
powershell
cd C:\work\1_Projects\aurelius\agents\java\onboarding-kyc
mvn spring-boot:run

Wait for "Started". Check: http://127.0.0.1:8201/health

9. Actuary (risk, Java): port 8202
powershell
cd C:\work\1_Projects\aurelius\agents\java\risk-engine
mvn spring-boot:run

Wait for "Started". Check: http://127.0.0.1:8202/health

10. Pulse (market news, Go): port 8301
powershell
cd C:\work\1_Projects\aurelius\agents\go\market-pulse
go run ./cmd/pulse

Check: http://127.0.0.1:8301/health

11. Conductor (the brain): port 8000
powershell
cd C:\work\1_Projects\aurelius\agents\python\orchestrator
.\.venv\Scripts\Activate.ps1
python src\main.py

Check: http://127.0.0.1:8000/health

12. Atrium web app: port 5173
powershell
cd C:\work\1_Projects\aurelius\frontend\web
npm run dev

Open: http://127.0.0.1:5173 and sign in with advisor and your DEV_LOGIN_PASSWORD.

Rules to remember
Order: steps 1 to 3 first (data, security, CRM). Steps 4 to 10 in any order. Then the Conductor (11), then the web app (12) last.
Stop: press Ctrl+C in each terminal, in reverse order (12 back to 1).
If you change .env, restart everything, because each agent reads .env only when it starts.
Quick mode (just to see the web app): set MOCK_AGENTS=true in .env, then run only steps 11 and 12.

If a check page doesn't open, look at that terminal for the error and send it to me.