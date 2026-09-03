# Day 41 — Backend Integration

Read CLAUDE.md first. Read `docs/PROJECT_CONTEXT_Day36-onward.md` for what was built on
Days 36–40. Then come back here.

## What to build today

Replace ALL mock data with real API calls to the FastAPI backend at
`http://localhost:8000`. By the end of today, every page should show live data from the
real Neo4j graph and Qdrant index, with no mock imports remaining in the production code
path.

**IMPORTANT — read before starting:**
1. Start the backend services first and verify they're healthy before touching frontend
   code:
   ```bash
   cd ~/Layer_10_Project2
   docker compose up -d
   cd backend && source venv/bin/activate
   python scripts/run_server.py &
   curl http://localhost:8000/api/health
   ```
   Do not proceed until `/api/health` returns a successful response showing Neo4j and
   Qdrant are connected.

2. **Do NOT modify any backend code.** All changes are in `frontend/` only. If you
   discover a backend endpoint is missing a field or behaving unexpectedly, flag it — do
   not fix it yourself.

3. **Quota constraint on `/api/chat`:** each call consumes Gemini API quota
   (gemini-3.1-flash-lite). Test chat integration with **at most 2–3 deliberate calls**,
   not in a debug loop. All other endpoints are quota-free.

## Pre-task: Create an API client layer

Before wiring individual pages, create a centralized API client:

### `src/lib/api.ts`

A single file containing all API call functions. This replaces the mock functions
scattered across `src/mocks/*.ts`. Structure:

```typescript
const API_BASE = 'http://localhost:8000';

// Helper for GET requests
async function fetchApi<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(path, API_BASE);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }
  const response = await fetch(url.toString(), {
    headers: { 'X-User-Clearance': '4' }  // max clearance for dev
  });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

// Helper for POST requests
async function postApi<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Clearance': '4'
    },
    body: JSON.stringify(body)
  });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

// Exported API functions — one per endpoint
export async function sendChatMessage(question: string, sessionId: string | null) { ... }
export async function fetchEntities(type?: string, search?: string, skip?: number, limit?: number) { ... }
export async function fetchEntityDetail(id: string) { ... }
export async function fetchEntityClaims(id: string, claimType?: string) { ... }
export async function fetchEntityTimeline(id: string) { ... }
export async function fetchSubgraph(entityId: string, hops?: number) { ... }
export async function searchGraph(query: string) { ... }
export async function fetchEvidence(evidenceId: string) { ... }
export async function fetchHealth() { ... }
```

**CRITICAL: Entity IDs contain colons.** When building URL paths like
`/api/entities/${id}`, you MUST use `encodeURIComponent(id)`. Example:
`/api/entities/${encodeURIComponent('person:beck-sally:sally-beck-at-enron-com')}`

This applies to: `fetchEntityDetail`, `fetchEntityClaims`, `fetchEntityTimeline`,
`fetchSubgraph` — any function that puts an entity ID in the URL path.

## Page-by-page wiring

### 1. Chat Page (`ChatPage.tsx`)

Replace `mockChatApi()` calls with `sendChatMessage()` from the API client.

**Key changes:**
- Send real `{ question, session_id }` to `POST /api/chat`
- Handle the real `ChatResponse` shape — verify your TypeScript types in
  `src/types/chat.ts` match the actual response (check against
  `backend/src/api/models.py`)
- `session_id`: store from each response, send back on next request, reset to null
  on "New Chat"
- `effective_question`: should now appear on real follow-up questions
- `clarification`: should now appear on genuinely ambiguous queries

**Evidence drawer metadata gap:**
The real `CitationItem` from `/api/chat` does NOT include `message_date` or
`message_subject` — those were mock-only fields (see Day 37 gotcha in the project log).

**Fix:** When the evidence drawer opens (user clicks a citation badge), fetch
`GET /api/evidence/${citation.evidence_id}` to get `email_date` and `email_subject`.
Show a small loading state in the drawer's source metadata section while this fetch
is in flight. If the fetch fails, show "Source metadata unavailable" gracefully.

Remove `message_date` and `message_subject` from the `CitationItem` type — they should
not be expected from the chat response anymore.

**Testing:** use at most 2–3 real questions. Good test questions:
- "Who does Sally Beck report to?" (should return cited answer)
- "Tell me about her role" (follow-up — tests session_id and effective_question)
- Try a genuinely ambiguous name if you can think of one (tests clarification)

### 2. Graph Explorer (`GraphExplorerPage.tsx`)

Replace `mockFetchSubgraph()` with `fetchSubgraph()` from the API client.

**Key changes:**
- The search input should now call `searchGraph(query)` hitting
  `GET /api/graph/search?q=...` — this returns real entity matches, not just mock name
  matching
- Click-to-expand calls `fetchSubgraph(entityId, hops)` with real entity IDs
- Real entity IDs will contain colons — ensure `encodeURIComponent()` is used in the
  API call, not in the graph component's internal state (IDs in the graph's node objects
  stay un-encoded)

**Initial load:** pick a sensible default entity to show on first load. Options:
- Call `searchGraph('Sally Beck')` on mount and use the first result
- Or show the empty state with search focused — either works

**Expect much larger graphs than mocks.** Real subgraphs may have 15–30+ nodes at 2
hops. The force simulation settings from Day 38 (charge strength, collision radius, link
distance) may need slight tuning for larger node counts — adjust if things look too
cramped or too sparse with real data, but don't spend more than a few minutes on this.

**Remove the hops selector entirely.** Delete the 1-hop / 2-hop toggle from the
graph controls UI. All subgraph requests should always use `hops=1`. The 2-hop
option produced graphs that were too large and cluttered to be useful — this is a
deliberate scope reduction, not a bug. Remove the hops parameter from
`GraphControls.tsx` and hardcode `hops=1` in the `fetchSubgraph()` call.

**Double-click opens entity detail in a new tab.** Change the double-click-on-node
behavior to open `/entities/${encodeURIComponent(nodeId)}` in a **new browser tab**
(`window.open(..., '_blank')`) rather than navigating in the same tab. This matches
the evidence link behavior (Day 40) and prevents losing the current graph state.
Do NOT implement a GraphContext or state-lifting solution — the new-tab approach is
the chosen fix for graph state loss.

**Directed edges for asymmetric relationships.** The graph has 8 relationship types.
Two are symmetric (undirected): `works_with` and `negotiating_with`. The remaining
six are asymmetric (directed): `reports_to`, `requests_from`, `informs`,
`made_by`, `affects`, `party`. For asymmetric relationships, render the edge with
a **visible arrowhead** pointing from source to target, so the direction is clear
(e.g., "Sally Beck --reports_to--> John Lavorato"). For symmetric relationships
(`works_with`, `negotiating_with`), render without arrowheads. react-force-graph-2d
supports directed links via `linkDirectionalArrowLength` and
`linkDirectionalArrowRelPos` — use these, and conditionally set arrow length to 0
for symmetric relationship types.

### 3. Entity List Page (`EntitiesPage.tsx`)

Replace `mockFetchEntities()` with `fetchEntities()` from the API client.

**Key changes:**
- Type filter and search now hit `GET /api/entities?type=...&search=...&skip=...&limit=...`
- Pagination is now real — total count comes from the API, skip/limit drive real pages
- The search input now searches server-side — note what matching behavior you observe
  (does it match aliases? is it case-insensitive?) and report in the end-of-day summary

### 4. Entity Detail Page (`EntityDetailPage.tsx`)

Replace mock functions with real API calls:
- `fetchEntityDetail(id)` for the header
- `fetchEntityClaims(id, claimType)` for the Claims tab
- `fetchEntityTimeline(id)` for the Timeline tab
- The Relationships tab already calls subgraph — wire it to `fetchSubgraph(id)`

**Key changes:**
- Entity ID from `useParams()` must be `decodeURIComponent()`'d before use in display,
  and `encodeURIComponent()`'d when passed to API functions
- Claims filtering by type is now server-side
- Timeline data comes from the real temporal query engine
- Handle cases where an entity ID from the URL doesn't exist in the graph — show a
  "not found" state, don't crash

### 5. Evidence Page (`EvidencePage.tsx`)

Replace `mockFetchEvidence()` with `fetchEvidence()` from the API client.

**Key changes:**
- `GET /api/evidence/${evidenceId}` returns the full evidence detail including
  `email_body`, `email_date`, `email_subject`, `evidence_quote`
- The quote-highlighting logic (find `evidence_quote` in `email_body` and highlight it)
  should work the same way — just with real text now
- Real email bodies may be much longer and messier than mocks — verify the layout
  handles long emails with nested quotes, forwarded headers, etc.

### 6. Health Page (`HealthPage.tsx`)

This page is still a placeholder — Day 42 will build the full health dashboard.
However, since it's trivial, optionally wire a basic version now:
- Call `fetchHealth()` hitting `GET /api/health`
- Display the returned status (Neo4j connected, Qdrant connected, node/edge counts)
- A simple card or two showing the numbers is sufficient — Day 42 will build the
  full dashboard

This is optional — skip if time is short.


## Cleanup: mock files

After all pages are wired to real API calls:
- **Do NOT delete the mock files** (`src/mocks/*.ts`). Move them to a clearly-labeled
  location or add a comment at the top of each saying "// Mock data — not used in
  production. Kept for reference and potential testing." They're useful reference for
  the expected data shapes and for any future testing.
- **Remove all mock imports** from page/component files. No production code path should
  import from `src/mocks/`.
- Verify with a project-wide search: `grep -r "mocks/" src/ --include="*.tsx" --include="*.ts"`
  should only show hits inside the `mocks/` folder itself, not in pages or components.

## Error handling

Every API call should have proper error handling:
- **Network errors** (backend not running): show a clear "Cannot connect to backend"
  message, not a blank page or cryptic error
- **404s** (entity/evidence not found): show a "not found" state specific to that page
- **500s** (backend internal error): show a generic "Something went wrong" with a Retry
  button
- **Timeout:** if a request takes more than 10 seconds, show a timeout message

The chat page already has error/retry handling from Day 37 — extend the same pattern
to other pages.

## Scope boundaries — do NOT do these today

- Do not modify backend code
- Do not build the full health dashboard (Day 42)
- Do not build merge audit log or conflict review queue (Days 43–44)
- Do not add authentication beyond the hardcoded `X-User-Clearance: 4` header
- Do not add caching, request deduplication, or optimistic updates

## When you are done

Follow section 11 of CLAUDE.md. In addition to the standard summary, specifically note:
1. Whether `/api/entities?search=` matches aliases and is case-insensitive (or not)
2. Whether any backend response shape differed from what the frontend types expected
   (list every mismatch found and how it was handled)
3. Whether the evidence drawer's metadata fetch (from `/api/evidence/`) worked correctly
4. How many real `/api/chat` calls were made during testing
5. Report what was done, append summary to `docs/PROJECT_CONTEXT_Day36-onward.md`,
   suggest a commit message, and stop.