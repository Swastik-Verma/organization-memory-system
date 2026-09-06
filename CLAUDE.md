# CLAUDE.md — Layer 10 Project 2 (Organizational Memory System)

> This file is read automatically at the start of every Claude Code session.
> Read it fully before taking any action.

---

## 1. What this project is

An **organizational memory system** built on the Enron email corpus. It extracts structured
facts from raw emails using an LLM, stores them in a Neo4j knowledge graph with full evidence
trails, indexes evidence in Qdrant for semantic search, and exposes everything through a
hybrid RAG chatbot with inline citations.

This is a **portfolio / resume project**, targeting interviews. It is intended to be
production-realistic, not a demo toy.

**The backend (Weeks 1–5, Days 1–35) is complete and was hand-built deliberately, slowly,
for learning.** It is not to be treated as scratch code.

**The frontend (Weeks 6–7, Days 36–48) is being delegated to you.** The goal here is speed
and quality of output, not learning — but the same engineering standards apply.

---

## 2. Required reading before you start work

At the beginning of every session, read these in order:

1. `docs/Full_Project_Plan/org_memory_system(Layer10)_full_plan.md` — the canonical 56-day plan.
   **This plan is never renumbered, compressed, or reordered.**
2. `docs/PROJECT_CONTEXT_Day36-onward.md` — the running log of everything built during this
   frontend phase. **This is the most important file for knowing current state.**
  
3. `docs/Full_Project_Plan/PROJECT_CONTEXT(Layer10)_Day36-41.md` — decisions, design
   rationale, backend changes, and the open backlog from Week 6. Read this for *why*
   things were built the way they were, not just *what* was built.

Read these only when you need deeper background on how the backend works:

- `docs/Full_Project_Plan/PROJECT_CONTEXT(Layer10)_Day29-35.md` — **most relevant one.** Retrieval
  engine, FastAPI endpoints, chatbot, response shapes. Read this before touching any
  API-facing code.
- `docs/Full_Project_Plan/PROJECT_CONTEXT(Layer10)_Day22-28.md` — graph schema, temporal model
- `docs/Full_Project_Plan/PROJECT_CONTEXT(Layer10)_Day15-21.md` — deduplication, entity resolution
- `docs/Full_Project_Plan/PROJECT_CONTEXT(Layer10)_Day8-14.md` — extraction pipeline
- `docs/Full_Project_Plan/PROJECT_CONTEXT(Layer10)_Day5-7.md` — ontology, parsing
- `docs/Full_Project_Plan/PROJECT_CONTEXT(Layer10)_Day1-4.md` — environment setup

Do not re-read all of these every session. Read what the current task actually needs.

---

## 3. Current status

- **Days 1–35 complete.** Full backend pipeline works end to end.
- **Day 35 evaluation code is written but deliberately NOT executed** — it is deferred to
  Week 8 by explicit decision. Do not run it.
- **Week 6 (Days 36–41) is the current phase:** React frontend core.
- `frontend/` is where all new work goes.

---

## 4. Repository layout

```
Layer_10_Project2/
├── CLAUDE.md                          # this file
├── .env                               # secrets — NEVER read, print, or commit
├── docker-compose.yml                 # Neo4j + Qdrant, memory-capped
├── requirements.txt
├── data/
│   ├── raw/                           # corpus (gitignored)
│   ├── processed/                     # intermediate outputs (gitignored)
│   └── outputs/
├── backend/
│   ├── venv/
│   ├── src/
│   │   ├── parsing/                   # Week 1
│   │   ├── extraction/                # Week 2
│   │   ├── deduplication/             # Week 3
│   │   ├── graph/                     # Week 4
│   │   ├── retrieval/                 # Week 5 (Days 29–31)
│   │   ├── api/                       # Week 5 (Day 32) — FastAPI app + routes
│   │   ├── chatbot/                   # Week 5 (Days 33–34)
│   │   └── evaluation/                # Week 5 (Day 35) — written, not run
│   └── scripts/
├── frontend/                          # ← ALL your work goes here
└── docs/
    ├── ONTOLOGY.md
    ├── EXTRACTION_CONTRACT.md
    ├── PROJECT_CONTEXT_Day36-onward.md   # running log — you append to this
    └── Full_Project_Plan/                # reference docs, read-only
```

**Note the non-standard layout:** `data/`, `.env`, and `requirements.txt` live at the
**project root**, not inside `backend/`.

---

## 5. Hard rules

### Scope
- **Never modify anything under `backend/`.** Read it freely to understand the API contract,
  but do not edit backend files. If you believe a backend change is genuinely required,
  stop and explain why — I will decide.
- **Never modify `docs/Full_Project_Plan/`.** Those files are historical record.
- **Never modify `docker-compose.yml`, `.env`, or `requirements.txt`** without asking first.
- All new code goes in `frontend/`.

### Git
- **Never run `git commit`, `git push`, `git reset`, `git checkout`, or any history-altering
  git command.** I commit manually at the end of every day. You may run read-only git
  commands (`git status`, `git diff`, `git log`) freely.

### One plan-day per session
- Each session covers **exactly one plan-day**. When that day's scope is complete, **stop.**
- Do not begin the next day's tasks, even if you have remaining context, even though the
  full plan file shows you what comes next. The next day's instructions will come from me
  as a fresh prompt.
- Finishing early is fine. Report completion and wait.

### Ask before deciding
- The daily plan I give you defines the scope. If something is ambiguous, or you need to
  make an architectural decision the plan does not cover (new dependency, different library,
  restructured folder layout, changed data flow), **stop and ask.** Do not decide silently.
- Explain what you are about to do before making large or sweeping changes.

### Environment
- Machine is **WSL2/Ubuntu on a Windows laptop with 8GB RAM.** Keep everything lightweight.
- Do not suggest or install heavy tooling. Do not run all Docker services simultaneously
  unless the task genuinely requires it.
- Do not install global npm packages without asking.

---

## 6. Frontend tech stack (per the plan)

| Layer | Choice |
|---|---|
| Framework | React + Vite + TypeScript |
| Styling | Tailwind CSS |
| Components | shadcn/ui |
| Graph visualization | react-force-graph |
| Charts | Recharts |

Stick to these. If you think an alternative is meaningfully better, ask first — do not
substitute silently.

---

## 7. Backend API — what you are building against

The FastAPI backend runs at **`http://localhost:8000`**. Interactive docs: `/docs`.

Start it with:
```bash
cd ~/Layer_10_Project2/backend && source venv/bin/activate
python scripts/run_server.py
```

**Endpoints available:**

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/chat` | Full pipeline: question → answer + citations + claims |
| GET | `/api/entities` | Paginated list, filter by type/search |
| GET | `/api/entities/{id}` | Single entity detail |
| GET | `/api/entities/{id}/timeline` | Chronological claims |
| GET | `/api/entities/{id}/claims` | Filterable by claim_type / status |
| GET | `/api/graph/{id}/subgraph` | 1–2 hop neighborhood (nodes + edges) |
| GET | `/api/graph/search` | Cross-type search (Person / Org / Deal / Decision) |
| GET | `/api/evidence/{id}` | Evidence detail + source email body |
| GET | `/api/health` | Neo4j + Qdrant connectivity and counts |
| GET | `/api/conflicts` | Claims with non-empty `conflicts_with` |
| GET | `/api/review-queue` | `status='review'` OR `confidence<0.5` OR has conflicts |

**Not yet built** (will be needed for Days 43–44, flag it when you get there):
merge list, merge undo, ingest trigger.

**Auth:** simplified for now. Send an `X-User-Clearance` header with value `"1"`–`"4"`.
It defaults to clearance `4` if absent. This is deliberately not production-secure.

---

## 8. API contract details that will bite you

Read `docs/Full_Project_Plan/PROJECT_CONTEXT_Day29-35.md` §10 for the full list. The
critical ones:

1. **Entity IDs contain colons and email slugs.**
   Example: `person:beck-sally:sally-beck-at-enron-com` — *not* `person:beck-sally`.
   **URL-encode these carefully in routes.** Use `/api/graph/search?q=Sally` to find real IDs.

2. **`clarification.options` is the only source of "did you mean" information.** It is a
   structured field on the response and is deliberately *not* present in the `answer` text.
   The UI must render it from the structured field. Do not also parse it out of `answer` —
   that causes double-rendering (this was a real bug in Week 5).

3. **`citation.evidence_quote` can be empty** for some claims. Needs a graceful empty state.

4. **`ChatResponse.session_id`** must be echoed back on the next request to continue a
   multi-turn conversation.

5. **`ChatResponse.effective_question`** is populated only when a follow-up question was
   rewritten into a standalone one. Good candidate for a subtle "interpreted as…" UI hint.

6. **The 5 valid claim types (closed vocabulary):**
   `reports_to`, `works_with`, `negotiating_with`, `requests_from`, `informs`

7. **Entity node types:** Person, Organization, Deal, Decision.

---

## 9. LLM API quota — use mocks while building

The chatbot is currently configured to use **`gemini-3.1-flash-lite`** (set via
`GEMINI_CHAT_MODEL` in `.env`). This is a deliberate downgrade from `gemini-3.6-flash`,
which is capped at **20 requests/day** on the free tier and was exhausted repeatedly during
Week 5 testing. `gemini-3.6-flash` will be switched back on only for the final demo
recording and the Week 8 evaluation.

`flash-lite` has a much higher allowance, but it is **not unlimited**, and every call to
`/api/chat` consumes quota (1 chatbot call + 1 query-parse call, plus 1 more if it is a
follow-up).

**Therefore, while building UI:**

- **Develop against mock data, not the live `/api/chat` endpoint.** Create fixture JSON
  matching the real `ChatResponse` shape (answer, citations, claims, clarification,
  session_id, effective_question) and build the interface against that.
- Hit the live endpoint only when you genuinely need to verify real integration — and when
  you do, a **small number of deliberate calls**, not repeated calls in a debug loop.
- **Day 41 is the designated backend-integration day.** Before then, mocks are the default.
- Read-only endpoints (`/api/entities`, `/api/graph/*`, `/api/evidence/*`, `/api/health`)
  do **not** consume LLM quota — they only touch Neo4j/Qdrant. You may call these freely.

If you find yourself about to call `/api/chat` more than two or three times in a session,
stop and use a mock instead.

---

## 10. Working style

- **Explain before you build.** For anything non-trivial, say what you intend to do and why,
  in plain language, before writing the code.
- **Root causes, not surface patches.** If something breaks, explain *why it worked before
  and broke now*, not just what you changed.
- **I do not have deep frontend knowledge, and that is intentional.** Explain frontend
  concepts in plain language when they matter to a decision. Do not assume React/CSS
  fluency. Do not pad explanations with jargon.
- **I will question your work.** Treat pushback seriously — real bugs were caught this way
  throughout Weeks 1–5. If I am wrong, say so directly and explain. If I am right,
  acknowledge it plainly and fix it.

---

## 11. End of every session

When the day's scope is complete:

1. **Report what was done** — files created, files modified, decisions made, anything
   deferred or left incomplete.
2. **Append a concise summary to `docs/PROJECT_CONTEXT_Day36-onward.md`** under a
   `## Day N — <title>` heading. Keep it factual and useful to a future session that has
   no memory of today. Include: what was built, key decisions and why, gotchas discovered,
   and anything a later day will need to know.
3. **Suggest a one-line commit message.** Do not commit it. I will.
4. **Stop.** Do not start the next day.

## Deferred Decisions (added Day 43)

These decisions were made during the project and should not be revisited
without explicit instruction.

### Build vs. evaluate split (Day 35 decision)
- Days 43, 44: BUILD the UI and endpoints now. DEFER actually undoing merges
  or resolving conflicts to Week 8 (after baseline evaluation runs).
- Day 48: Build integration test infrastructure. Defer acting on the bug list.
- Days 49-50: Entire final evaluation and fix pass deferred to the end.
- Day 35 baseline evaluation code was never saved to disk — must be REBUILT
  from scratch in Week 8.

### Day 34 known flaws accepted as-is
- Follow-up resolver limitations (missed bare pronouns, false positives,
  wrong referent, hard 5-turn cutoff, no unresolvable escape hatch) are
  documented interview talking points, not defects to close.
- The proposed fix (prompt Rule 6 + rewritten==question check) was
  explicitly declined. Do not implement unless asked.

### Merge undo scope
- Undo restores entity identity only (names, aliases, emails, mention_count).
- Claims are NOT reassigned — the mapping of which claims belonged to which
  pre-merge identity was never captured in the pipeline.
- Day 16 exact merges are not undoable via the UI (deterministic; "undo" =
  re-run the script).
- This is a documented limitation, not a bug.

### Evidence quote highlighting
- CONFIRMED BROKEN (verified Day 42 against live data — 5 of 8 sampled quotes
  failed the plain `includes()` check; all 8 passed after whitespace normalization).
- Root cause: `SourceEmail.tsx` → `renderBody()` uses `email_body.includes(quote)`
  with no whitespace normalization, unchanged since Day 40. LLM-extracted quotes
  collapse whitespace; raw stored bodies preserve hard line breaks.
- Fix: normalize both strings identically before matching, but highlight against
  the original unnormalized body (it renders verbatim in a `<pre>`).
- Deliberately not fixed on Day 42 per that day's brief. Tracked in KNOWN_ISSUES.md M1.

### Missing email To: field
- Message nodes have no to_addr property. The raw emails have it; the Week 1
  parser never extracted it. Fixing requires full re-ingestion. Accepted as
  a known limitation — do not attempt to fix.

### Open backlog carried from Week 6 (Days 36–41 handoff)

- ⚠️ HIGH PRIORITY — The chatbot needs a dedicated, thorough debugging pass
  across all question types, entity types (especially Deal/Decision, barely
  tested), ambiguous names, follow-ups, and questions with no good answer in
  the corpus. Not a minor fix — flagged emphatically, deserves its own
  session(s). Best scheduled after the frontend phase or alongside Week 8.
- Clarification loop bug (Day 33–34 code): asking "Who does Sally Beck report
  to?" produces a garbled clarification option ("Fernley Dyson and Sally
  Beck" as one candidate), and selecting an option re-clarifies instead of
  resolving — never reaches an answer. Likely a defect in how clarification
  options are generated/deduped. Week 8 entity-resolution work may reduce how
  often this triggers but won't fix the underlying formatting/looping defect.
- Citation numbers appear out of sequential order in chat answers (e.g.
  14, 6, 10, 5, 2...). Each number still links to the correct evidence —
  nothing is broken, just visually non-sequential. Low priority; confirm
  whether renumbering by first appearance is worth doing.
- N+1 query pattern on the claims endpoint (`/api/entities/{id}/claims`) —
  one extra Cypher round-trip per claim, measured at 1.24s for 247 claims.
  Accepted tradeoff for now; optional future fix is batching evidence into
  one query.
- Node radius caps at 20 in the graph explorer — entities above ~150
  mentions render at identical size. Pre-existing Day 38 scale decision.
  The user explicitly does not want this changed — recorded here only so
  it isn't mistaken for a bug and "fixed" by accident.