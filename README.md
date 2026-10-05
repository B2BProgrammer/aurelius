# Aurelius - Advisor Intelligence Swarm

A polyglot multi-agent system that helps wealth advisors spend less time on
admin and more time with clients.

## Port map
| Component            | Port |
|----------------------|------|
| Conductor (Python)   | 8000 |
| Python agents        | 8001-8004 |
| Node agents          | 8101-8102 |
| Java agents          | 8201-8202 |
| Go agent             | 8301 |
| MCP advisor-tools    | 8500 |
| ChromaDB             | 8600 |
| React console        | 5173 |

## Build steps
- [x] Step 01 - Folder structure
- [ ] Step 02 - Shared agent contract (JSON schema)
- [ ] Step 03 - Conductor orchestrator + LLM client
- [ ] Step 04 - RAG: ingestion + Librarian agent
- [ ] Step 05 - MCP server + Analyst agent
- [ ] Step 06 - Sentinel security agent
- [ ] Step 07 - Node agents
- [ ] Step 08 - Java agents
- [ ] Step 09 - Go agent
- [ ] Step 10 - React console
- [ ] Step 11 - docker-compose, end-to-end test



```mermaid
sequenceDiagram
    autonumber
    actor A as Advisor
    participant UI as Atrium (React)
    participant C as Conductor (Python)
    participant S as Sentinel (Python)
    participant LI as Liaison (Node)
    participant SC as Scribe (Python)
    participant AN as Analyst (Python)
    participant N as Notary (Java)
    participant P as Pulse (Go)
    participant AC as Actuary (Java)
    participant L as Librarian (Python)
    participant H as Herald (Node)

    rect rgb(232, 240, 254)
    Note over A,C: Phase 1 - Sign in and ask
    A->>UI: Sign in (SSO)
    A->>UI: "Prep me for my 2pm review with the Patel household"
    UI->>C: Request + JWT token
    end

    rect rgb(254, 236, 236)
    Note over C,S: Phase 2 - Input guard
    C->>S: Check request for PII and prompt injection
    S-->>C: Safe, PII masked
    end

    rect rgb(236, 248, 236)
    Note over C,P: Phase 3 - Plan and gather facts (in parallel)
    C->>C: LLM plans which agents to call
    par CRM
        C->>LI: Get household profile and open tasks
        LI-->>C: Patel profile, 2 open tasks
    and Meetings
        C->>SC: Summarize last meeting notes
        SC-->>C: Summary + 3 action items
    and Portfolio
        C->>AN: Check drift, concentration, tax-loss ideas
        AN-->>C: Equity 8 percent over target, 1 tax-loss idea
    and Onboarding
        C->>N: Check KYC status
        N-->>C: ID document expires next month
    and Markets
        C->>P: Recent events affecting their holdings
        P-->>C: Earnings miss on a top holding
    end
    end

    rect rgb(255, 246, 229)
    Note over C,L: Phase 4 - Deeper analysis
    C->>AC: Run retirement projection on current portfolio
    AC-->>C: 82 percent probability of success
    C->>L: Find firm research on the flagged holding
    L-->>C: Research summary with source citations
    end

    rect rgb(243, 236, 252)
    Note over C,H: Phase 5 - Draft client communication
    C->>H: Draft follow-up email in advisor's voice
    H-->>C: Draft email
    end

    rect rgb(254, 236, 236)
    Note over C,S: Phase 6 - Output guard
    C->>S: Check briefing and email (suitability, PII, disclosures)
    S-->>C: Approved, disclosure added
    end

    rect rgb(232, 240, 254)
    Note over A,C: Phase 7 - Human in the loop
    C-->>UI: Meeting briefing + draft email
    UI-->>A: Show briefing and draft for review
    A->>UI: Edit and approve email
    UI->>C: Approved
    C->>LI: Log meeting prep note and tasks in CRM
    LI-->>C: Saved
    C-->>UI: Done
    end

    rect rgb(245, 245, 245)
    Note over P,UI: Background - Pulse runs all day
    P-->>C: Alert: big move in a stock 40 clients own
    C-->>UI: Push notification to advisor
    end

```



# 🏗️ Aurelius: System Architecture

```mermaid
flowchart TD
    User((👤 Advisor))

    Web["🖥️ Atrium Web<br/>React + TypeScript<br/>localhost:5173"]
    Mobile["📱 Atrium Mobile<br/>Flutter<br/>Android / iOS / Chrome"]

    User -->|Opens a household| Web
    User -->|Opens a household| Mobile
    Web -->|HTTPS + advisor JWT| Conductor
    Mobile -->|HTTPS + advisor JWT| Conductor

    subgraph Swarm["Aurelius Agent Swarm (service token between agents)"]
        Conductor["🎼 Conductor: Supervisor<br/>Python / FastAPI<br/>localhost:8000"]

        Librarian["📚 Librarian: RAG<br/>Python<br/>localhost:8001"]
        Analyst["📊 Analyst: Portfolio<br/>Python<br/>localhost:8002"]
        Scribe["📝 Scribe: Meetings<br/>Python<br/>localhost:8003"]
        Herald["✉️ Herald: Emails<br/>TypeScript<br/>localhost:8101"]
        Liaison["🗂️ Liaison: CRM<br/>TypeScript<br/>localhost:8102"]
        Notary["🪪 Notary: KYC / AML<br/>Java Spring Boot<br/>localhost:8201"]
        Actuary["🧮 Actuary: Risk / Retirement<br/>Java Spring Boot<br/>localhost:8202"]
        Pulse["⚡ Pulse: Market News<br/>Go<br/>localhost:8301"]

        Conductor -->|1. Policy search| Librarian
        Conductor -->|2. Portfolio analysis| Analyst
        Conductor -->|3. Meeting summary| Scribe
        Conductor -->|4. Draft email| Herald
        Conductor -->|5. Household and tasks| Liaison
        Conductor -->|6. KYC check| Notary
        Conductor -->|7. Risk and retirement| Actuary
        Conductor -->|8. Market events| Pulse
        Herald -->|Client context| Liaison
        Pulse -.->|Live events SSE| Conductor
    end

    Sentinel{"🛡️ Sentinel<br/>Security Guard<br/>PII / Injection / Compliance<br/>localhost:8004"}
    Conductor <-->|Checks every input and output| Sentinel

    MCP["🔌 MCP Server<br/>advisor-tools<br/>localhost:8500"]
    Analyst -.->|Holdings| MCP
    Actuary -.->|Holdings| MCP
    Pulse -.->|Holdings| MCP

    Chroma[("🧠 ChromaDB<br/>Vector store")]
    Docs[("📄 Firm documents")]
    CRM[("🗂️ CRM data")]
    KYC[("🪪 KYC docs + watchlist")]
    Notes[("📝 Meeting notes")]
    Holdings[("💼 Holdings data")]

    Librarian -.->|Semantic search| Chroma
    Docs -.->|Ingest| Chroma
    Liaison -.-> CRM
    Notary -.-> KYC
    Scribe -.-> Notes
    MCP -.-> Holdings

    Claude["🤖 Claude Haiku 4.5<br/>Anthropic API"]
    Conductor -->|Plan + write answer| Claude

    classDef ui fill:#2f5bd3,stroke:#1c2b30,color:#fff
    classDef boss fill:#e07b1a,stroke:#7a3d00,color:#fff
    classDef agent fill:#2e9e5b,stroke:#1d5e37,color:#fff
    classDef guard fill:#3b2fd3,stroke:#1c1680,color:#fff
    classDef data fill:#4a5670,stroke:#2a3142,color:#fff
    classDef llm fill:#3b2fd3,stroke:#1c1680,color:#fff

    class Web,Mobile ui
    class Conductor boss
    class Librarian,Analyst,Scribe,Herald,Liaison,Notary,Actuary,Pulse agent
    class Sentinel guard
    class Chroma,Docs,CRM,KYC,Notes,Holdings,MCP data
    class Claude llm
```