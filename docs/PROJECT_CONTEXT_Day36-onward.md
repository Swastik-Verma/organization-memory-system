# Project Context — Day 36 onward (Frontend, Weeks 6–7)

> Running log for the frontend build. Read this in full at the start of every session in
> this phase — it is the most important file for knowing current state.

---

## Day 36 — Project setup and design system

### What was built

**Environment note (not part of the plan's task list, but blocking):** WSL2 had no
Node.js — only a Windows install at `/mnt/c/Program Files/nodejs/`, which is unreliable
for Vite's file-watching/HMR across the WSL↔Windows filesystem boundary. Asked the user
and installed **nvm** + **Node v24.20.0 LTS** natively inside WSL2 (`~/.nvm`). Every
`npm`/`npx`/`node` command in this project must run with nvm sourced first:
```bash
export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
```
This isn't automatic in a fresh shell yet — nvm appended its init block to `~/.bashrc`
during install, so a new interactive shell should pick it up, but non-interactive tool
shells (like this agent's Bash tool) do not source `~/.bashrc` and need the two lines
above run explicitly each time.

**Scaffolded** `frontend/` with Vite + React + TypeScript (`npm create vite@latest .
-- --template react-ts`). This pulled in a very current Vite template:
- **Vite 8**, **TypeScript ~6.0**, **React 19**
- `oxlint` instead of ESLint (Vite's own current default) — kept it, no reason to swap
- No `tailwind.config.ts` or `postcss.config.js` — **Tailwind v4** is CSS-first config
  and ships its own Vite plugin (`@tailwindcss/vite`), so those files from the plan's
  suggested structure don't exist and aren't needed. Config lives in `src/index.css`
  via `@theme inline` and CSS custom properties.

**Installed:** `tailwindcss` + `@tailwindcss/vite`, `react-router-dom`, and shadcn/ui via
`npx shadcn@latest init -d`. shadcn's current CLI (v4) installed `@base-ui/react` instead
of Radix primitives and used its `base-nova` style — this is simply what the current
`shadcn/ui` package ships as of today, not a substitution of a different library.

**Path aliases:** `@/*` → `./src/*`, configured in `tsconfig.json`, `tsconfig.app.json`,
and `vite.config.ts` (`resolve.alias`). Note: TypeScript 6.0 deprecates `baseUrl` — paths
are resolved relative to the tsconfig file itself now, so `baseUrl` was deliberately left
out (with it, `tsc -b` throws `TS5101`).

**Design system** (`frontend/src/index.css`):
- Main content area: light/neutral (`--background`, `--foreground`, etc., mostly
  shadcn's generated neutral oklch values, left as-is).
- Sidebar: fixed dark theme via shadcn's dedicated `--sidebar-*` tokens (`#0f172a` bg,
  slate-200 text) — **not** the `.dark` class/toggle. There is no dark-mode toggle in
  this app; the sidebar is permanently dark and the content area permanently light by
  design, so the `.dark` variant block was deleted from the generated CSS and
  `@custom-variant dark (&:is(.dark *))` was kept only so shadcn's generated
  `dark:` component classes stay inert (scoped to a `.dark` class that's never applied)
  rather than reacting to the OS `prefers-color-scheme`.
- Accent (interactive elements — links, active nav, buttons): indigo `#4f46e5`
  (`--primary`), sidebar's own accent for the active nav highlight is `#6366f1`.
- Entity type colors, registered as Tailwind utilities (`bg-entity-person`,
  `text-entity-organization`, etc. via `@theme inline`):
  - Person: `#3b82f6` (blue)
  - Organization: `#8b5cf6` (violet)
  - Deal: `#10b981` (emerald)
  - Decision: `#f59e0b` (amber)
- Font: Geist Variable (`@fontsource-variable/geist`, pulled in by shadcn init) —
  clean, professional, dashboard-appropriate. One family, hierarchy done via Tailwind
  text-size utilities (page title `text-2xl font-semibold`, body `text-sm`, captions
  `text-sm text-muted-foreground`) rather than custom CSS classes.
- `--radius` set to `0.5rem` (down from shadcn's default `0.625rem`) for a slightly
  crisper, more data-dense feel.

**Layout shell:**
- `src/components/layout/Sidebar.tsx` — fixed `w-60` dark sidebar, `h-svh`, does not
  scroll with content.
- `src/components/layout/NavLink.tsx` — wraps `react-router-dom`'s `NavLink`, applies
  the active-state styling (`bg-sidebar-primary` when active).
- `src/components/layout/MainLayout.tsx` — sidebar + `<main>` with independent
  `overflow-y-auto` scroll, renders routed content via `<Outlet/>`.
- Sidebar nav has **exactly 4 links** per the plan's spec (Chat, Graph Explorer,
  Entities, Health) — `/conflicts` and `/merges` have routes (below) but intentionally
  no sidebar entry yet; the plan surfaces those from the Health dashboard on Day 42.

**Routing** (`src/App.tsx`, `react-router-dom`): all 8 routes from the plan's table,
`/` redirects to `/chat`, unknown paths render `NotFoundPage`. Placeholder pages live in
`src/pages/*.tsx`, all rendering through a small shared `src/components/PagePlaceholder.tsx`
(title + description) rather than duplicating the same JSX 8 times.

### Verification

Could not get a real browser open in this environment — Playwright's Chromium needs
`libnspr4`/`libnss3` system libs that aren't installed, and there's no `sudo` access to
install them (`sudo: a password is required`). Flagging this now since Day 37+ UI work
will hit the same wall.

As a substitute, ran a real DOM/React verification via `@testing-library/react` + `jsdom`
+ `vitest` (installed ephemerally with `--no-save`, removed afterward — not in
`package.json`). Confirmed, with actual rendered DOM assertions:
- `/` redirects to `/chat`
- All 4 nav links render; Chat is active by default (`bg-sidebar-primary`,
  `aria-current="page"`)
- Clicking Graph Explorer / Entities / Health navigates, updates the URL, highlights the
  clicked link, and un-highlights the previous one
- The `<aside>` sidebar DOM node is the *same node* before and after navigation (not
  remounted) — confirms no layout jump
- `/entities/:id` and `/evidence/:id` render with the id interpolated correctly
- Unknown routes render the 404 page

Also ran `tsc -b` (clean), `npm run build` (clean, ~264KB JS / 25KB CSS gzipped to
~84KB/5KB), and `oxlint` (clean except one expected warning inside shadcn's
generated `button.tsx`, not our code).

**Not done:** an actual pixel/visual check in a real browser window. If Playwright/browser
testing is wanted going forward, the system needs `libnspr4`, `libnss3`, and related libs
installed via `apt-get install -y <playwright's list>`, which requires `sudo`.

### Gotchas for future sessions

- Always source nvm before any `npm`/`node` command in a fresh Bash tool call — see top
  of this entry.
- Tailwind v4 config lives in `src/index.css`, not a JS/TS config file.
- No dark-mode toggle exists or is planned; don't add `.dark` class logic without asking.
- No real browser available for visual/screenshot verification — see above.

### Suggested commit message

```
Day 36: React frontend scaffold — Vite/TS/Tailwind v4/shadcn, dark sidebar layout, routed placeholder pages
```

---

## Day 37 — Chat Interface

### What was built

Replaced the Day 36 `/chat` placeholder with a fully functional chat interface, built
entirely against mock data (no calls to the real `/api/chat` — that's Day 41).

**New shadcn primitives added** (`npx shadcn add`): `sheet` (evidence drawer — built on
`@base-ui/react/dialog`, same as Day 36's Button), `badge`, `skeleton` (unused today,
kept for later), `input`.

**Types** (`src/types/chat.ts`) — mirrors `backend/src/api/models.py` field-for-field
(`ChatResponse`, `CitationItem`, `ClarificationInfo`, `ClarificationOption`,
`ChatRequest`), plus a UI-only `ConversationEntry` union (`user` / `assistant` / `error`)
for local chat state. Deliberately typed against the real Pydantic models rather than
the simplified shape in the day's task brief — see gotcha below.

**Mock layer** (`src/mocks/chatMocks.ts`) — `mockChatApi(question, sessionId)` simulates
`POST /api/chat`: ~0.9–1.3s delay, then routes to one of four fixtures by keyword in the
question, so every UI state is reachable from the input box during manual testing:
- default → happy path, 4 citations, all fields populated (Sally Beck / reports_to chain)
- question contains "john" (not "lavorato") → `clarification` non-null, 3 options
- question contains "global crossing" or "deal" → citations with empty `evidence_quote`
- question contains "her "/"she "/starts with "what about", and a session already
  exists → `effective_question` populated (simulates a follow-up rewrite)
- question contains "error" → the mock throws, driving the error+Retry UI

**Components:**
- `components/chat/ChatMessage.tsx` — renders one turn (user bubble / assistant bubble
  / error card). Contains `AnswerText`, which splits the answer string on `/(\[\d+\])/g`
  and renders each `[N]` as a `CitationBadge` looked up by `citation.index` — text that
  doesn't match a real citation index falls back to plain text instead of a dead badge.
- `components/chat/CitationBadge.tsx` — small clickable pill, opens the evidence drawer.
- `components/chat/ClarificationCard.tsx` — renders `clarification.message` +
  `clarification.options` as pill buttons, each with a colored dot reusing the existing
  `--entity-*` design tokens from Day 36 (person/organization/deal/decision) keyed off
  `option.type`. Per CLAUDE.md §8.2, this reads only the structured `clarification`
  field — never parses `answer` for it.
- `components/chat/EffectiveQuestion.tsx` — de-emphasized "Interpreted as: …" hint,
  rendered above the assistant bubble when `effective_question` is non-null.
- `components/chat/ChatMessageList.tsx` — scrollable message list; auto-scrolls to
  bottom on new entries via a sentinel ref + `scrollIntoView`; empty state shows 4
  suggested prompts (one per mock fixture, including a labeled "Trigger a network error
  (demo)" chip) that call the same send handler as manual input.
- `components/chat/ChatInput.tsx` — pinned input bar, disabled while loading, clears on
  send, submits on Enter via a native `<form>`.
- `components/evidence/EvidenceDrawer.tsx` — shadcn `Sheet` slide-out (right side),
  closes on X / outside click / Escape (all free from `@base-ui/react/dialog`). Shows
  claim-type badge (colored via new `src/lib/claimTypes.ts`), subject → object, a
  confidence bar, the evidence quote (or a graceful "No verbatim quote available"
  fallback when empty), and a `Link` to `/evidence/:id` (Day 40's page, currently a
  placeholder) built from `evidence_id`.
- `pages/ChatPage.tsx` — orchestrator. Owns `entries`, `sessionId`, `isLoading`,
  `lastQuestion` (for retry), and drawer state. `session_id` is threaded through every
  mock call and reset to `null` by a "New Chat" button (which also clears `entries`).

**Layout change (`components/layout/MainLayout.tsx`):** the Day 36 layout wraps every
routed page in a `max-w-5xl px-8 py-8` div inside a `<main className="overflow-y-auto">`
— i.e., the whole page scrolls together. A chat UI needs the opposite: message list
scrolls independently while the input stays pinned to the viewport bottom. Rather than
force the pinned input to fight page-level scroll, `MainLayout` now checks the route
(`pathname.startsWith('/chat')`) and skips the padded/page-scroll wrapper for chat only,
letting `ChatPage` own its own `h-full flex flex-col` layout with an internal
`overflow-y-auto` region. Every other route is untouched. This will likely need revisiting
on Day 39 (Graph Explorer), which probably wants similar full-bleed treatment.

### Gotchas for future sessions

- **API contract mismatch in the Day 37 task brief, resolved in favor of the plan (user
  decision):** the brief's mock `CitationItem` example includes `message_date` and
  `message_subject`. The real `CitationItem` model (`backend/src/api/models.py`) has
  neither field — only `marker`, `index`, `claim_id`, `claim_type`, `subject_name`,
  `object_name`, `evidence_quote`, `evidence_id`, `confidence`. First pass matched the
  real model and omitted them from the drawer; the user explicitly asked for the source
  metadata section back, so `CitationItem` in `src/types/chat.ts` now carries
  `message_date: string | null` and `message_subject: string | null` as **mock-only
  fields**, called out in a comment as not present on the real backend model. The mock
  fixtures in `src/mocks/chatMocks.ts` populate them (one citation in the empty-quote
  fixture deliberately leaves both `null` to exercise the drawer's graceful fallback —
  "No source message metadata available for this citation."). The drawer renders a
  "Source" section below the evidence quote showing the subject line and date, or that
  fallback when both are missing.
  **Known gap carried into Day 41:** the real `/api/chat` response won't have these
  fields. Before wiring the real endpoint, either (a) ask about adding `message_date`/
  `message_subject` to the backend's `CitationItem` (a backend change — needs sign-off
  per CLAUDE.md §5, not made here), or (b) have the drawer fetch
  `GET /api/evidence/{evidence_id}` (`EvidenceDetailResponse`, which already carries
  `email_date`/`email_subject`) when it opens, and drop the mock-only fields. Flag this
  at the start of Day 41 rather than rediscovering it mid-session.
- **`ClarificationOption` is an object**, not a plain string (`{id, name, type}`), despite
  the day brief's `["Sally Beck (person)", ...]` example. Built against the real model.
- **Bug found by the user via manual testing, fixed same session:** `mockChatApi`'s
  keyword router originally checked `q.includes('john') && !q.includes('lavorato')` for
  the clarification trigger. Clicking a clarification option resends `option.name` as a
  literal new question (`"John Arnold"`, `"John Lavorato"`, `"John Zufferli"`) — so
  "John Arnold" and "John Zufferli" still contain `"john"` and re-triggered the same
  clarification card instead of resolving, while "John Lavorato" skipped the
  clarification branch but matched nothing else and fell through to the default
  `NORMAL_RESPONSE` (the unrelated Sally Beck reports-to answer). Fixed by adding three
  dedicated fixtures (`JOHN_ARNOLD_RESPONSE`, `JOHN_LAVORATO_RESPONSE`,
  `JOHN_ZUFFERLI_RESPONSE`, each with its own claims/citations about the deal) and
  checking exact-string matches (`q === 'john arnold'`, etc.) *before* the generic
  `q.includes('john')` clarification trigger. General lesson for any future mock router
  in this app: a keyword-routed mock must be tested along every UI-driven path that
  re-sends text as a new question (clarification options, suggested prompts), not just
  by typing into the input box — the two don't always hit the router the same way.
- DOM verification used the same ephemeral vitest + jsdom + testing-library approach as
  Day 36 (installed with `--no-save`, fully removed after — `package.json` and
  `package-lock.json` are byte-identical before/after). No `sheet`/dialog-specific
  jsdom gaps were hit beyond `scrollIntoView`, which jsdom doesn't implement and needed
  a one-line polyfill in the test setup file. If real-browser Playwright testing becomes
  available later (still blocked on missing `libnspr4`/`libnss3`, no `sudo`), that
  polyfill won't be needed.
- `sheet.tsx`/`badge.tsx`/`input.tsx` all build on `@base-ui/react` primitives (consistent
  with Day 36's Button/shadcn setup) — `Sheet`'s outside-click/Escape-to-close behavior
  comes for free from `@base-ui/react/dialog`, nothing custom was wired for it.

### Verification

- `tsc -b && vite build` — clean.
- `oxlint` — clean except the same two pre-existing shadcn-generated warnings from Day 36
  (`button.tsx`, `badge.tsx`), not app code.
- Real DOM test (ephemeral vitest, removed after): rendered `ChatPage` and drove it with
  `@testing-library/user-event` through all 6 states — empty state with suggestions,
  send → loading → cited answer with 4 clickable citation badges → evidence drawer
  content (claim type, confidence %, quote, source metadata), empty-`evidence_quote`
  graceful fallback,
  clarification card → clicking an option sends it as a new question, error → Retry →
  recovers, and New Chat resetting the conversation. All 6 passed.
- No real browser available (same Playwright/system-lib blocker as Day 36) — no pixel-level
  visual check was done.

### Not done / deferred

- Real `/api/chat` integration — Day 41 by design.
- The full evidence page at `/evidence/:id` — Day 40 by design; today's drawer links to
  it but the route still renders the Day 36 placeholder.
- No dark-mode, no localStorage persistence, no streaming — none were in scope.

### Suggested commit message

```
Day 37: chat interface — mock-backed chat UI with inline citations, evidence drawer, clarification handling
```

---

## Day 38 — Graph Explorer

### What was built

Replaced the Day 36 `/graph` placeholder with an interactive force-directed graph
explorer, built entirely against mock data (no calls to the real `/api/graph/*` — that's
Day 41, per the task brief).

**Installed:** `react-force-graph-2d` (and its `force-graph`/d3-force transitive deps).
Clean install, no peer-dependency conflicts with React 19.

**Types** (`src/types/graph.ts`) — mirrors `backend/src/api/models.py`'s Graph section
field-for-field (`GraphNode`, `GraphEdge`, `SubgraphResponse`, `GraphSearchResult`,
`GraphSearchResponse`), same approach as Day 37's `chat.ts`. One mock-only addition:
`GraphEdge.claim_count` (for edge thickness) — the real `GraphEdge` model has no
equivalent field, flagged in a comment, same pattern as `chat.ts`'s
`message_date`/`message_subject`.

**Mock layer** (`src/mocks/graphMocks.ts`) — 4 fixture subgraphs (Sally Beck, John
Lavorato, the Global Crossing deal, Enron America as centers), 5-8 nodes / 4-7 edges
each, covering all 4 entity types and all 5 claim types across the set, mention_count
ranging 6-82. `mockFetchSubgraph(entityId, hops)` returns a `structuredClone` of the
matching fixture (so callers can't mutate shared state across calls) after a ~250-400ms
delay, or a small 3-node fallback for any unmapped entity ID. `mockSearchEntities(query)`
searches a directory built from all mock node names, case-insensitive substring match,
sorted by `mention_count` descending. Verified with an ephemeral `tsx` script (installed
`--no-save`, removed after — `package.json`/`package-lock.json` confirmed byte-identical
before/after): node-count/edge-count bounds, all edge endpoints resolve to real nodes, ID
format, entity/claim type coverage, mention_count range, deep-copy isolation, and search
behavior all pass. 40/40 checks passed.

**Components:**
- `components/graph/GraphCanvas.tsx` — `react-force-graph-2d` wrapper. Fully custom
  `nodeCanvasObject`/`nodePointerAreaPaint` (circle radius on a clamped sqrt scale of
  `mention_count`, 4-20px; fill color from `entityTypeColor`; an indigo ring drawn around
  already-expanded nodes; truncated name label below each node) and
  `linkCanvasObject` in `'after'` mode (draws the relationship-type text at each edge's
  midpoint on a light background chip, on top of the default-rendered line so
  `linkColor`/`linkWidth` still apply). Container is sized via `ResizeObserver` on a
  wrapper div (the library needs explicit pixel `width`/`height`, no auto-100%).
  Hover tooltip position is tracked in graph coordinates and re-projected to screen
  coordinates on every `onZoom`/`onZoomEnd`/`onEngineTick`, so it stays pinned to the
  node through pan/zoom/simulation movement.
- `components/graph/NodeTooltip.tsx` — small presentational tooltip (name, type, mention
  count), absolutely positioned, `pointer-events-none`.
- `components/graph/GraphControls.tsx` — header ("Graph Explorer" + a one-line
  click-vs-double-click hint), search input + submit button, a 1-hop/2-hop toggle (two
  `Button`s, no new shadcn primitive needed), and a Reset button.
- `pages/GraphExplorerPage.tsx` — orchestrator. Owns two `Map`s (`nodeMapRef`,
  `edgeMapRef`) mutated in place and "committed" to array-typed state on every change;
  existing node objects keep referential identity across merges specifically so
  react-force-graph preserves their `x`/`y` simulation position instead of re-scattering
  the whole layout on every expand — only the top-level array reference is new, which is
  what the library needs to detect additions. Edge de-duplication key is
  `source::type::target`. Loads the Sally Beck neighborhood on mount as the initial view
  (chose "populated" over "empty state with a prompt" per the brief's either-is-fine
  guidance). Search replaces the current graph (clears both maps, merges in the new
  fixture); expand-by-click merges into the existing graph without clearing it, matching
  §4 of the brief.

**No new shadcn primitives needed** — search input reuses `Input`, hops toggle and reset
reuse `Button` with variant swapping, no `select`/`toggle-group` install required.

**Layout change (`components/layout/MainLayout.tsx`):** extended the Day 37 full-bleed
check from `pathname.startsWith('/chat')` to also match `/graph`, for the same reason —
the canvas needs to fill `<main>` directly, not sit inside the padded page-scroll wrapper.

### Interaction design

- **Single click** on a node: expands it (merges its mock neighborhood into the graph,
  marks it with an expanded ring, centers the view on it).
- **Double click**: navigates to `/entities/{id}`.
- `react-force-graph`/`force-graph` has **no built-in dblclick event**
  (`node_modules/force-graph/src/index.d.ts` only exposes `onNodeClick`) — implemented
  manually in `GraphCanvas` via a 260ms timer: a click defers the expand action; a second
  click on the *same* node within the window cancels the deferred expand and fires
  navigate instead. This means every single click has a ~260ms delay before it visibly
  expands — a known, deliberate tradeoff of the manual-double-click pattern, not a bug.

### Gotchas for future sessions

- **Important Day 41 topology gotcha, found while reading the backend route to build
  these mocks:** the real graph does **not** have direct Person→Person or Person→Org
  edges for claims. Claims are their own Neo4j nodes — relationships are modeled as
  `Person <-[:SUBJECT]- Claim -[:OBJECT]-> Person` (see `backend/src/graph/loader.py`'s
  `SUBJECT`/`OBJECT` edge creation, confirmed against `backend/src/api/routes/graph.py`'s
  `MATCH (n {id: $node_id})-[r]-(neighbor)` query). So a real `depth=1` subgraph around a
  Person will surface neighboring **Claim** nodes, not other Person/Org entities directly
  — reaching another Person takes `depth=2`, with a Claim node as the intermediate hop.
  Today's mocks instead show direct entity-to-entity edges (matching the task brief's
  example shape, and what's actually useful to look at), so this session's visual
  topology won't match the real API response as-is. Before Day 41 wiring, decide whether
  to (a) always request `depth=2` and collapse/hide the Claim hop in the merge logic, or
  (b) render Claim nodes as a 5th node type. Flag this at the start of Day 41 rather than
  rediscovering it mid-session.
- The real `/graph/{id}/subgraph` route also never actually populates `GraphEdge.claim_type`
  or `GraphEdge.confidence` (both stay `null` — only `type`, the raw Neo4j relationship
  name, is set). The mocks populate all three for a fuller-looking UI today; expect those
  two fields to come back empty on Day 41 regardless of what the mocks show.
- Real backend entity `type` values are lowercase (`"person"`, not `"Person"` —
  `backend/src/api/routes/graph.py` explicitly lowercases `labels(neighbor)[0]`).
  `src/lib/entityTypes.ts` is keyed lowercase for this reason; don't "fix" it to
  capitalized keys later without re-checking the route.
- **No real browser available in this environment** (same Playwright/`libnspr4`/`libnss3`
  blocker as Days 36-37, no `sudo`) — and unlike Days 36-37's DOM-only components, the
  graph canvas can't be substituted with a jsdom render either: `react-force-graph-2d`
  needs a real 2D canvas context, which jsdom doesn't provide without the native `canvas`
  package (itself blocked by the same missing system libs). Verification this session was
  therefore: `tsc -b` clean, `vite build` clean, `oxlint` clean (same 2 pre-existing
  shadcn warnings as Days 36-37, nothing new), plus the ephemeral mock-data script
  described above. **The interactive canvas itself (rendering, click-to-expand, hover
  tooltip, double-click navigation, zoom/pan) was not visually or interactively verified**
  — this is a real gap, not a formality, and should be the first thing checked if a real
  browser becomes available.
- Production JS bundle grew from ~264KB (Day 36) to ~545KB gzipped ~175KB, entirely from
  `force-graph`'s d3-force dependency tree. Expected and not addressed today (code-splitting
  wasn't in scope) — Vite's build warns about the >500KB chunk; revisit only if bundle size
  becomes a real concern later.

### Not done / deferred

- Real `/api/graph/*` integration — Day 41 by design.
- Filter panel (entity type / time range / confidence threshold) and edge-click claim
  detail, both listed in the canonical plan's one-line Day 38 summary — explicitly out of
  scope per this session's detailed task brief's "Scope boundaries" section (edges are
  display-only today; no filter panel; single click expands, double click navigates
  instead of the plan's single-click-to-profile). Flagged here in case a future session
  reads only the canonical plan and expects them already present.
- 3D graph, right-click context menu, minimap/overview panel, persisting graph state
  across navigation — none were in scope.

### Post-session fix: mock data identity bug (same-day follow-up)

Reported: clicking to expand "West Trading Desk" produced three different-looking entities
("West Trading Desk", "West Trading Desk — Contact A", "— Contact B") instead of merging
into the one already on screen.

**Root cause**: it was never an ID-consistency bug in the 4 authored fixtures — those
already reused the same `const` (ID + label) everywhere a shared entity appeared. The bug
was in `mockFetchSubgraph`'s fallback branch: any node that appeared *inside* a fixture but
had no fixture *of its own* (i.e. wasn't a `MOCKS` key — `West Trading Desk`, `Louise
Kitchen`, `Fletcher Sturm`, `Kenneth Lay`, `Approve Global Crossing Deal`, `August 2001
Reorganization` all qualified) fell through to the generic fallback generator, which
invents synthetic `"{label} — Contact A/B"` nodes with fabricated IDs on every expand. So
expanding a shared entity spawned fake new entities instead of revealing its real,
already-known neighbors.

**First fix attempt (incomplete — see below)**: added 6 dedicated fixtures for every entity
appearing inside more than one of the original 4 fixtures, but deliberately left the four
single-occurrence leaf entities (Finance, Enron Legal, Global Crossing Ltd, John Zufferli)
on the generic fallback, reasoning that "no more data past this point" was acceptable leaf
behavior. **That decision was wrong.** The fallback doesn't render as "no more data" — it
renders as two entity-*looking* nodes, so clicking any leaf reproduced the exact same
confusion. The user hit it again immediately on `Finance` (seeing `"Finance — Contact B"`
next to `"Finance — Cont…"`, the latter being `"Finance — Contact A"` truncated by the
canvas's 15-char label limit) and asked for a full-file audit rather than another
per-instance patch.

**Second fix (structural, current state)**: reworked `graphMocks.ts` so the bug class can't
recur:

1. **Single `ENTITIES` registry** — one canonical `{label, type, mention_count}` per ID.
   Fixtures build nodes by ID lookup (`node(SALLY_BECK)`) instead of repeating the name
   literal at each call site, so one entity carrying two different names is no longer
   expressible. `node()` throws on an unregistered ID.
2. **All 14 entities now have fixtures** (added Finance, Enron Legal, Global Crossing Ltd,
   John Zufferli) — every visible node expands to real, consistently-identified data.
3. **Fabricating fallback deleted.** An unknown ID now returns the centre node alone with
   no edges — never invented neighbours.
4. **`validateMockIntegrity()`** (exported, and auto-run under `import.meta.env.DEV` with
   `console.error`) enforces: one name per ID and one ID per name; each fixture contains its
   own centre; node labels match the registry; every edge endpoint is a node in the same
   fixture; and every entity referenced anywhere has its own fixture. That last invariant is
   precisely the one whose absence caused this bug both times.
5. `mockSearchEntities` now builds its directory from `ENTITIES` rather than by walking
   fixtures, so search results carry byte-identical identity to graph nodes.

Verified with the same ephemeral-`tsx` pattern (md5sums of `package.json`/`package-lock.json`
confirmed unchanged before/after): **134/134 checks passed**, including a full cross-fixture
audit building `id → set(names)` and `name → set(ids)` over every node of every fixture
(all sets size 1, for name, type, and mention_count), no `"Contact"`-style placeholder
anywhere, search identity matching graph identity for all 14 entities, and an idempotence
check confirming that expanding every node twice settles at exactly **14 nodes / 30 edges**
with no growth on the second pass. `tsc -b`, `oxlint`, and `vite build` all clean. The
canvas itself remains **unverified in a real browser** — same standing gap noted above.

**Lesson for future days**: don't leave part of a known-buggy code path in place because the
remaining cases seem benign. Prefer deleting the path that can produce the bad state, and
add an assertion so a regression fails loudly instead of surfacing in the UI later.

### Post-session fix: graph layout / label overlap

Reported: node and edge labels overlapped badly at the default zoom ("Louise Kitchen" over
"works_with", "Sally Beck" over "August 2001 Re…"), and edges were too faint to see.

**Root cause of the failed first attempt**: the `useEffect` that configured `d3Force` used
`[]` deps, but `<ForceGraph2D>` is only rendered once the `ResizeObserver` reports a
non-zero size. On first render `fgRef.current` was still `undefined`, the effect hit its
`if (!fg) return` guard, and **no force configuration was ever applied** — the graph ran on
stock d3 defaults (charge `-30`, link distance `30`) the whole time. The effect now depends
on `[isReady, nodes.length]`.

**Two facts about force-graph worth knowing for later days** (both read out of
`node_modules/force-graph/dist/force-graph.mjs`):

1. It never calls `zoomToFit`. Zoom is auto-set to `ZOOM2NODES_FACTOR / cbrt(nodeCount)`
   with `ZOOM2NODES_FACTOR = 4`, re-applied on every data change unless the user has
   manually zoomed. So 7 nodes ⇒ ~2.09x, 14 nodes ⇒ ~1.66x.
2. Node radii are in graph units (so they scale with zoom) but labels are drawn at a fixed
   screen size (`fontPx / globalScale`). A label's footprint in graph units is therefore
   `widthPx / scale` — any spacing rule that ignores this works at one zoom and breaks at
   another. This is why the collision radius is scale-aware.

**Fix** — new `src/components/graph/graphForces.ts` holds the tuning and label geometry
(shared so a test can exercise the real thing, not a copy):

- charge strength `-400`; link distance `260px / scale` (~124 graph units at 7 nodes)
- a hand-written collision force with radius `max(circleRadius, labelHalfWidth/scale) +
  16px/scale`. Written by hand rather than importing `d3-force-3d`: force-graph depends on
  it internally but it is **not** a declared dependency of this app, and a label-aware
  radius was needed anyway. If a declared dep is preferred later, swapping in
  `d3.forceCollide().radius(...)` is a drop-in.
- edge labels are skipped when the link is too short on screen to hold the text, and a
  per-frame declutter pass (`onRenderFramePre` seeds occupied boxes with every node label
  *and* node circle) skips any edge label that would land on occupied space. Node labels
  always win; they identify the entities.
- node labels keep their below-the-circle position and gained a translucent backing chip.
- `EDGE_COLOR` `#cbd5e1` → `#1e293b` (near-black) for visibility on the near-white canvas.

**Verified** with a headless layout harness: ran the real d3-force-3d simulation (the same
library force-graph uses) with the real `graphForces` config on the real fixtures, 500
ticks, then computed label/circle boxes at each fixture's default zoom and checked every
pair for intersection. Results — old defaults vs new config: Sally Beck 16 → **0**, Enron
America 15 → **0**, Louise Kitchen 10 → **0**, John Lavorato 9 → **0**, Global Crossing
Deal 5 → **0**; merged 8-node view **0** (1 of 11 edge labels hidden); fully expanded
14-node/30-edge graph **0** (6 of 30 edge labels hidden). The harness independently
reproduced the exact overlaps from the reported screenshot under the old settings, which is
good evidence the model matches the real renderer. `tsc -b`, `oxlint`, `vite build` clean.

Caveat unchanged: this verifies geometry and physics, not pixels. It cannot catch a
font-metric discrepancy (text width is estimated at `0.55em/char`, since there is no canvas
`measureText` in this environment) or anything about actual rendering. **Still not visually
confirmed in a browser.**

### Post-session fix: stuck hover tooltip

Reported: after clicking a node to expand it, that node's tooltip stayed visible permanently
— no amount of hovering elsewhere or clicking other nodes would clear it. Also: moving to
empty canvas didn't hide it, and clicking empty canvas did nothing.

**Root cause.** `hovered` was a single piece of React state holding *both* which node is
hovered and where to draw the tooltip. `handleZoomOrPan` — wired to `onEngineTick` so the
tooltip could follow a moving node — read `hovered` from its closure and **wrote it back**.
That made the tick loop a continuous re-assertion of hover state:

1. Clicking to expand adds nodes, which triggers `d3ReheatSimulation()`, so engine ticks
   fire continuously for several seconds.
2. Moving the pointer to empty canvas fires `onNodeHover(null)` exactly **once**.
3. The in-flight tick closure — captured while a node was still hovered — fires immediately
   after and calls `setHovered({ oldNode })`, resurrecting it.
4. That re-render recaptures the closure with the *restored* non-null value, so it
   re-asserts itself on the next tick, forever. A one-shot clear cannot win against a
   continuous stream of re-assertions.

This is why the bug was specific to click-to-expand: that is what reheats the simulation.

**Fix.** New `src/components/graph/tooltipController.ts` separates identity from position:

- Only `hover()` / `clear()` may change *which* node is showing.
- `syncPosition()` may only move an already-showing tooltip — it early-returns when nothing
  is hovered, so it can never create or revive one.
- Identity lives in a plain variable inside the controller, not a captured closure value, so
  the tick handler always reads current truth. The handlers are `useCallback([])`-stable and
  reach the controller through a ref, so force-graph never holds a stale closure.
- Added `onBackgroundClick` → `clear()` (clicking empty canvas hides the tooltip; there was
  no handler for this at all before).
- Added an effect that clears the tooltip if its node leaves the graph (e.g. a search
  replaces the view while the pointer is over a node) — nothing would fire a hover-out then.

The controller is built inside an effect rather than during render because its projection
function reads `fgRef`; this also satisfies oxlint's `react(refs)` rule cleanly instead of
suppressing it.

**Verified** by driving the real controller through the reported scenarios headlessly (it is
plain state by design, so no browser needed): 20/20 checks passed — hover shows; leaving to
empty canvas hides; node→node swaps; background click hides; and the main case: hover a
node, fire 200 ticks, leave the node, fire 200 more ticks, tooltip stays hidden, and normal
hovering resumes afterwards. Also confirmed the test is meaningful by re-implementing the
*old* closure-recapture design and showing it does reproduce the stuck tooltip. `tsc -b`,
`oxlint`, `vite build` all clean. Still not visually confirmed in a browser.

### Suggested commit message

```
Day 38: interactive graph explorer — react-force-graph-2d, click-to-expand, hover tooltips, mock subgraph data

Fix mock data identity bug: single canonical ENTITIES registry, fixtures for all 14
entities, no more fabricated "— Contact A/B" placeholder nodes, plus a dev-time
integrity check enforcing one-name-per-ID and full expandability.

Fix graph layout: force config was never applied (effect ran before the canvas
mounted); add scale-aware collision force, stronger charge, longer links, label
decluttering, and a darker edge color.

Fix stuck hover tooltip: the engine-tick handler re-asserted hover state from a
stale closure, so clearing it never stuck. Split identity from position into a
testable tooltip controller; add background-click-to-dismiss.
```

---

## Day 39 — Entity List and Entity Detail Pages

### What was built

Replaced the Day 36 `/entities` and `/entities/:id` placeholders with real, fully
functional pages, built entirely against mock data (no calls to the real
`/api/entities/*` — that's Day 41).

**Installed:** shadcn's `tabs` primitive (`npx shadcn add tabs`), built on
`@base-ui/react/tabs` — same pattern as every other shadcn component in this app. No new
npm dependencies (base-ui and cva were already installed); `package.json`/
`package-lock.json` are unchanged.

**Types** (`src/types/entity.ts`) — mirrors `backend/src/api/models.py`'s Entity section
field-for-field (`EntityListItem`, `EntityListResponse`, `EntityDetailResponse`,
`ClaimResult`, `EntityClaimsResponse`, `TimelineEvent`, `EntityTimelineResponse`), same
approach as Day 37's `chat.ts` and Day 38's `graph.ts`. Mock-only additions, each flagged
in the file's header comment:
- `EntityListItem.claim_count` and `EntityDetailResponse.claim_count`/`first_seen`/
  `last_seen` — none of these exist on the real models.
- `ClaimResult.evidence_ids` — the real model has a generic `evidence: list[dict]`
  instead. The brief's `source_count` field is deliberately **not** stored separately —
  it's computed as `evidence_ids.length` wherever shown, so there's one number instead of
  two that could drift apart.

**Mock layer** (`src/mocks/entityMocks.ts`) — 20 entities across all 4 types, 22 claims
covering all 5 claim types (confidence 0.40–0.93, includes both `superseded` and `review`
statuses). Built with the same "single canonical source of truth" architecture Day 38 had
to retrofit after a real bug (see that day's "mock data identity bug" post-session fix):
- **14 of the 20 entities reuse the exact same ids** as `graphMocks.ts`'s registry (Sally
  Beck, Enron America, the Global Crossing deal, etc.) — copied as literal strings rather
  than imported, since `graphMocks.ts` doesn't export its constants and is a Day 38 file
  this session must not modify. This means the Graph Explorer's double-click navigation
  and this page's own Relationships tab (which calls `graphMocks.mockFetchSubgraph`
  directly) land on the same entity identity as everywhere else — not a disconnected mock
  universe. **Risk flagged in the file's own header comment:** if `graphMocks.ts`'s
  registry ever changes, these copied strings must be updated by hand — nothing catches
  that drift automatically since the files don't share code.
- **Claims are declared once**, in a single `CLAIMS` array, each built via a `claim()`
  helper that looks up `subject_name`/`object_name` from the entity registry rather than
  accepting them as literals — the same fix Day 38 applied to `graphMocks.ts` after
  finding that hand-typed names next to hand-typed ids can silently drift apart.
  `mockFetchEntityClaims`/`mockFetchEntityTimeline` both *filter* this one array
  (`subject_id === id || object_id === id`), exactly mirroring the real Cypher query in
  `backend/src/api/routes/entities.py` — a claim was never duplicated into two entities'
  hand-authored claim lists, so there's no way for the same fact to read differently from
  its two ends.
- **6 new standalone entities** (Jeffrey McMahon, Greg Whalley, Arthur Andersen, Enron
  Broadband Services, EOTT Energy Restructuring, Freeze 401(k) Trading Window) exist only
  to round the list out to 20 for pagination and to exercise the "zero claims" / "no known
  relationships" empty states — none of them have a `graphMocks.ts` fixture, so their
  Relationships tab honestly falls through to that file's no-fabrication fallback (center
  node only, no edges) rather than inventing neighbours.
- `validateEntityMockIntegrity()` (exported, auto-run under `import.meta.env.DEV` with
  `console.error`, same pattern as `graphMocks.ts`) checks: no two entities share a name;
  every claim's `subject_id`/`object_id` resolves to a registered entity; every claim's
  `subject_name`/`object_name` matches the registry (catches exactly the class of bug Day
  38 hit); every `claim_type` is one of the 5 valid types; confidence is in `[0, 1]`.

**Small additive changes to Day 36 lib files** (existing exports untouched, only new
exports added, so nothing that already imports these files changes behavior):
- `src/lib/entityTypes.ts` — added `ENTITY_TYPE_BADGE_CLASSES` / `entityTypeBadgeClass()`,
  static Tailwind classes (`bg-entity-person/10 text-entity-person`, etc.) for the pill
  badges used throughout today's pages. Static strings, not built from a template — a
  dynamically-constructed class name (e.g. `` `bg-entity-${type}` ``) wouldn't survive
  Tailwind v4's JIT scanner.
- `src/lib/claimTypes.ts` — added `CLAIM_STATUS_COLORS` / `claimStatusColor()` /
  `claimStatusLabel()` for the claim status pill (`active`/`superseded`/`review`), kept
  separate from the existing claim-*type* color map since status and type are different
  closed vocabularies.

**Components** (`src/components/entity/`):
- `EntityTypeBadge.tsx` — small colored pill, used on both pages and the Relationships tab.
- `EntityCard.tsx` — one row on the list page; the whole row is a `Link` to
  `/entities/{encodeURIComponent(id)}`.
- `EntityHeader.tsx` — detail page header: name, type badge, aliases (only rendered when
  non-empty), mention/claim counts, first/last seen, back-to-list link.
- `ClaimCard.tsx` — one claim: type badge, status badge, subject → object (the side that
  isn't the current entity is a clickable `Link`, the current entity's own name renders
  as plain text), a confidence bar, valid-from/valid-to (`null` valid_to renders as
  "Present"), and a "View evidence" link to `/evidence/{first evidence_id}` — or, when
  `evidence_ids` is empty, a graceful "No supporting evidence indexed yet." message
  instead of a dead link (mirrors the CLAUDE.md §8.3 empty-quote handling from Day 37's
  evidence drawer).
- `ClaimsTab.tsx` — claim-type filter chips (colored via the existing `claimTypeColor`),
  a Confidence/Date sort toggle (confidence descending is the default, matching the real
  endpoint's `ORDER BY c.confidence DESC`), loading skeleton, empty state.
- `TimelineTab.tsx` — vertical timeline, oldest-first (matches the real endpoint's
  `ORDER BY c.valid_from ASC`), a connector line via a single `border-l` div with an
  absolutely-positioned dot per entry rather than one border per row.
- `RelationshipsTab.tsx` — calls `graphMocks.mockFetchSubgraph(entityId, 1)` directly and
  renders the edges that touch the *current* entity as a flat list (filtered to
  `edge.source === entityId || edge.target === entityId`, since a fixture can contain
  edges between two of its *other* nodes — e.g. the Global Crossing deal fixture also
  contains a Zufferli↔Global Crossing Ltd edge that has nothing to do with the deal
  itself). Each row shows the connected entity (type badge + link), the relationship type,
  and `edge.claim_count` (the Day 38 mock-only field). Ends with a "View in Graph
  Explorer" link to `/graph` (styled via `buttonVariants` directly rather than wrapping a
  shadcn `Button`, since `@base-ui/react/button` takes a `render` prop, not shadcn's usual
  `asChild`, and a styled `Link` is simpler than threading that through).

**Pages:**
- `EntitiesPage.tsx` — type filter chips (All + 4 types) and a search input, both
  client-side against the mock (`mockFetchEntities` itself still takes `type`/`search`/
  `skip`/`limit` params and does the filtering, so the call shape matches the real
  endpoint even though today's data source is local). Page size 10. Changing the filter or
  search resets to page 1 — done by resetting `skip` in the *same* handler that changes
  the filter/search state, not in a separate `useEffect` watching them, specifically to
  avoid firing the fetch effect twice (once with a stale page number, once corrected) on
  every filter change.
- `EntityDetailPage.tsx` — reads `id` via `useParams()` and `decodeURIComponent()`s it
  (matching the `encodeURIComponent()` used everywhere a link to this route is built —
  Day 38's graph canvas double-click, today's `EntityCard`/`ClaimCard`/`RelationshipsTab`
  links). Not-found state (a thrown `Error` from `mockFetchEntityDetail` for an
  unregistered id) renders "Entity was not found" rather than crashing. shadcn `Tabs`
  defaulting to the Claims tab.

### Gotchas for future sessions

- **Real backend gap that will surface on Day 41, found while reading
  `backend/src/api/routes/entities.py` to build these mocks:** `GET /api/entities` only
  ever matches `(n:Person) OR (n:Organization)` — the `entity_type` query param maps
  `"person"`/`"organization"` to a label filter, and the "no filter" branch is hardcoded to
  `WHERE (n:Person OR n:Organization)` too. **Deal and Decision nodes are not reachable
  through this endpoint at all**, regardless of what filter is passed. `GET
  /api/entities/{id}` has the identical restriction (`WHERE ... (n:Person OR
  n:Organization)`), so a Deal or Decision id 404s there as well. Today's mocks support all
  4 types because the Day 39 brief explicitly asks for Deal/Decision in the type filter and
  in the 4 detailed profiles — but this means the "Deal" and "Decision" filter chips, and
  two of today's four detailed profiles (Global Crossing Transaction, August 2001
  Reorganization), have **no real backend equivalent to integrate against on Day 41** as
  the routes currently stand. This isn't something fixable from the frontend — flag it at
  the start of Day 41 rather than rediscovering it mid-session; the options are asking for
  a backend change to these two routes, or scoping the real `/entities` page down to
  Person/Organization only until that happens.
- The 14 shared ids between `entityMocks.ts` and `graphMocks.ts` are duplicated string
  literals, not an import — see the mock layer note above. A future edit to one file's
  registry (e.g. renaming an entity, or changing an id's slug) must be mirrored in the
  other by hand; nothing in either file's integrity check can catch that drift since
  neither imports the other.
- **New oxlint warning category, not seen in Days 36–38:** `react(set-state-in-effect)` on
  the 5 places that reset a piece of state to `null` at the top of a data-fetching
  `useEffect` (`EntitiesPage`, `EntityDetailPage`, `ClaimsTab`, `TimelineTab`,
  `RelationshipsTab`) before kicking off the mock fetch — this is what drives the loading
  skeleton for the *new* key (entity id, or a changed claim-type filter) instead of
  flashing the *previous* key's stale data. Investigated and left as-is: this is the
  standard "reset-then-fetch" shape for an async effect keyed on a changing id/filter, and
  the warning's suggested alternative ("derive during render") doesn't apply to data that
  only exists after an async call resolves. Treated the same way Days 36–38 treated the
  pre-existing shadcn-generated warnings (documented, not "fixed" by contorting the code
  around a lint heuristic that doesn't fit this case).
- Installing `shadcn add tabs` added a 3rd pre-existing-shadcn-generated oxlint warning
  (`tabs.tsx`'s `only-export-components`) alongside Day 36/37's `button.tsx`/`badge.tsx`
  ones — same category, not app code, not addressed for the same reason those weren't.
- `@base-ui/react/button` (shadcn's `Button`) takes a `render` prop, not the Radix-style
  `asChild` that shadcn docs/examples elsewhere sometimes assume. `Button asChild` silently
  doesn't type-check the way you'd expect from a Radix-based shadcn app. The
  "button-styled-Link" need in `RelationshipsTab.tsx` was solved by importing
  `buttonVariants` and applying it directly to the `Link`'s `className` instead.

### Verification

Same standing constraint as Days 36–38: no real browser available in this environment
(Playwright needs `libnspr4`/`libnss3`, no `sudo` to install them). All of today's UI is
plain DOM (no canvas), so — like Days 36–37 — real DOM verification was done via an
ephemeral `vitest` + `jsdom` + `@testing-library/react`/`user-event` install (`--no-save`,
fully removed afterward; `package.json`/`package-lock.json` md5s confirmed byte-identical
before and after). 15/15 checks passed, including: entity list sorted by mention_count
with correct pagination math (20 entities, page size 10 → "Page 1 of 2"); type-filter chips
narrow the list and hide pagination when the filtered set fits one page; search filters and
shows the empty state on no matches; clicking an entity card navigates to its detail page
with the URL-encoded id round-tripping correctly through `decodeURIComponent`; the detail
header renders name/aliases/claim count; the Claims tab defaults to confidence-descending
order, filters by claim type, and shows both `Active`/`Superseded` status badges and the
graceful "No supporting evidence indexed yet." state on a claim with no evidence; clicking
a claim's counterpart entity name navigates to *that* entity's own detail page; the
Timeline tab renders oldest-first; the Relationships tab renders `graphMocks` edge data
with a working `/graph` link; an unknown id shows the not-found state; and an entity with
no `graphMocks` fixture / no claims shows the relationships/claims empty states rather than
fabricated data. Also ran `validateEntityMockIntegrity()` itself as a unit check (0
problems). `tsc -b`, `oxlint` (clean except the pre-existing/new-but-accepted warnings
above), and `npm run build` all clean.

**Not done:** an actual pixel/visual check in a real browser window — same standing gap as
every prior day.

### Not done / deferred

- Real `/api/entities/*` integration — Day 41 by design.
- Entity editing, merging, deletion UI — explicitly out of scope per the brief.
- A mini graph inside the Relationships tab — it's a flat text list by design, per the
  brief's scope boundaries; the full graph lives at `/graph`.
- Cross-linking from the Day 37 chat/evidence-drawer components to entity pages — the
  brief explicitly says not to touch Day 37 chat components today; that link-up is Day 41
  by design.
- Debouncing the search input — every keystroke re-runs the mock filter (with its
  ~200–400ms artificial delay) rather than waiting for the user to pause typing. Not
  addressed today since the brief only asked for client-side filtering of the mock list;
  worth a look once the real endpoint's actual network latency is in the loop on Day 41.

### Post-session fix: Relationships tab mislabel, then a real cross-file count bug

Two rounds of user feedback after the day's initial build:

**Round 1 — mislabel.** The Relationships tab showed "Works With · 5 claims" next to each
connected entity. The number is `edge.claim_count` from `graphMocks.ts` — the count of
evidence sources backing that one merged relationship, the same concept as "Sources: 5" on
the Claims tab, not a count of separate claims. Relabeled to "5 sources" in
`RelationshipsTab.tsx`. Checked whether `EntityCard.tsx`/`EntityHeader.tsx`'s "X claims"
labels had the same problem — they don't: those read `entity.claim_count` from
`EntityDetailResponse`/`EntityListItem`, a genuinely different field (the entity's total
distinct-claim count), so they were left as-is.

**Round 2 — the numbers themselves disagreed.** The user then noticed the Kenneth Lay ↔
Enron America "Works With" relationship showed 2 sources on the Claims tab but 5 on the
Relationships tab for what should be the same underlying claim, and asked for a full audit
of every relationship shared between `entityMocks.ts` and `graphMocks.ts`, not just this
one instance.

Audited all 22 `CLAIMS` entries against all `graphMocks.ts` edges by matching on
`(subject_id, claim_type, object_id)`. Found **14 shared relationships** where the two
files' counts disagreed (entityMocks' `evidence_ids.length` vs. graphMocks'
`claim_count`), out of the pairs that exist in both files — most graph edges have no
entityMocks counterpart at all (different entity pairs entirely, e.g. Louise Kitchen
`reports_to` Kenneth Lay only exists in `graphMocks.ts`) and were correctly left alone, since
the user's ask was about relationships that appear in *both* files, not full topological
parity between them. 2 pairs (Enron Legal `requests_from` the Global Crossing deal;
Approve-GC-Deal `informs` the Global Crossing deal) already agreed and needed no change.

**Which file to treat as authoritative:** `entityMocks.ts`'s `evidence_ids` are lists of
specific (mock) evidence-id strings — the more granular, detailed representation. `graphMocks.ts`'s
`claim_count` was, per the Day 38 log, invented purely to drive edge-thickness on the
canvas, with no backing detail. Chose to treat `evidence_ids.length` as ground truth and
corrected `graphMocks.ts`'s 14 edge `claim_count` values to match, rather than inventing new
evidence-id strings to inflate entityMocks up to graphMocks' arbitrary numbers. Each of the
14 corrected values was updated everywhere it's duplicated across fixtures (several of
these edges are intentionally drawn from both entities' subgraphs, per `graphMocks.ts`'s own
header comment about exercising the merge/dedup path) — used `replace_all` on the exact
`edge(...)` call text specifically so every duplicate copy got the same fix in one pass,
rather than risking only fixing the copy the bug report happened to point at.

**Added a regression guard** (`validateGraphClaimConsistency()` in `entityMocks.ts`,
run under `import.meta.env.DEV` alongside the existing `validateEntityMockIntegrity()`):
calls `graphMocks.mockFetchSubgraph()` (graphMocks.ts's own public export — nothing reaches
into that file's internals) for every entity id referenced anywhere in `CLAIMS`, and cross-checks
every claim's evidence count against the matching edge's `claim_count`. **Verification
caught a real gap in the first version of this checker**: a plain last-write-wins `Map`
recording one `claim_count` per edge key missed the case where *graphMocks' own two copies
of the same edge* disagree with each other (reintroducing the original bug in only one of
Kenneth Lay's/Enron America's two fixture copies still passed, because whichever fixture
happened to be queried last still held the correct value, purely by luck of iteration
order). Fixed by recording every observed value per edge key in a `Set` instead of
overwriting, so the checker flags both failure modes: graphMocks disagreeing with itself
across fixtures, and graphMocks agreeing with itself but disagreeing with entityMocks.
Verified both cases explicitly by temporarily reintroducing each one (an ephemeral
`tsx` script, removed after — `package.json`/`package-lock.json` md5s confirmed unchanged)
and confirming the checker caught each, then confirming it reports 0 problems on the
corrected data.

**Lesson for future days**, consistent with the one already recorded for Day 38's mock
identity bug: two independently-hand-authored mock files describing overlapping facts is a
standing source of exactly this bug class. The `entityMocks.ts` header comment already
flagged the *id-string* duplication risk between the two files; this add-on check narrows
the remaining gap by catching *count* drift automatically, though it still can't catch a
future edit that changes an id string in one file without the other (that would just make
the two files stop describing the same entity at all, which is a different, still-unguarded
risk noted in the same header comment).

### Suggested commit message

```
Day 39: entity list and detail pages — filterable/searchable entity browser,
tabbed Claims/Timeline/Relationships profile view, mock data layer shared with
the Day 38 graph explorer's entity identities

Fix Relationships tab mislabel ("X claims" -> "X sources") and a real
cross-file data bug: 14 relationships shared between entityMocks.ts and
graphMocks.ts had disagreeing source/claim counts. Reconciled graphMocks.ts's
edge claim_count values to entityMocks.ts's evidence_ids as ground truth, and
added a dev-time cross-file consistency check to catch future drift.
```

---

## Day 40 — Evidence Detail Page

### What was built

Replaced the Day 36 `/evidence/:id` placeholder with a full evidence detail page showing
the "trust chain": claim → extracted quote → source email, built entirely against mock
data (no calls to the real `/api/evidence/{id}` — that's Day 41).

**Pre-task fix applied first, per the brief:** the two existing "View evidence" links —
`EvidenceDrawer.tsx` (Day 37) and `ClaimCard.tsx` (Day 39) — now open `/evidence/:id` in a
new tab (`target="_blank" rel="noopener noreferrer"`), so drilling into evidence no longer
loses chat/graph/entity page state. Grepped the whole codebase for any other route to
`/evidence/*` first (per the standing "fix the whole class, not just the reported
instance" rule) — confirmed these were the only two.

**Types** (`src/types/evidence.ts`) — mirrors `backend/src/api/models.py`'s
`EvidenceDetailResponse` field-for-field, same approach as every prior day's type file.
The real field is `quote`, not `evidence_quote` as the brief's example JSON shows — kept
as `quote` to match the backend model (chat.ts made the same call on Day 37). Real fields
the UI doesn't need today (`message_id`, `char_start`, `char_end`, `evidence_verified`)
are omitted with a comment, same as chat.ts omitting `claims`/`entities`/`retrieval_info`/
`context_text`. Mock-only additions, flagged in the header: `subject_id`/`object_id` (the
real model has only names, no ids — needed for the claim section's entity links),
`status`/`valid_from`/`valid_to` (these live on the Claim node in the real schema, not the
Evidence node — confirmed by reading the Cypher query in
`backend/src/api/routes/evidence.py`, which never selects them), and `email_to` (real
model has only a single `email_from`).

**Mock layer** (`src/mocks/evidenceMocks.ts`) — two tiers:
- **5 hand-authored "showcase" fixtures** covering the required states: `evidence_2210`
  (happy path, matches the brief's own example exactly — confidence 0.85, 2 recipients),
  `evidence_3390` (genuinely empty quote, sourced from chatMocks.ts's real
  `EMPTY_QUOTE_RESPONSE`), `evidence_1980` (22-line negotiation-update email), `evidence_1750`
  (status `superseded` with a non-null `valid_to`), `evidence_2260` (4 recipients).
- **33 "filler" fixtures** generated from a transcribed table of every other evidence_id
  referenced by `chatMocks.ts` citations or `entityMocks.ts` claims (38 distinct ids total
  across both files), so every citation badge and "View evidence" link already built on
  Days 37/39 resolves to a real mock instead of 404ing. `chatMocks.ts`-sourced fillers keep
  their real quote text; `entityMocks.ts`-sourced fillers have no quote text at all in the
  source file (`ClaimResult` only carries evidence_id strings), so one is synthesized from a
  small claim-type-keyed template (e.g. `works_with` → "X has been working closely with Y on
  this.") and embedded into a shared boilerplate email body. Neither source file exports its
  raw fixture arrays, and this session isn't scoped to add exports to Day 37/39 files, so the
  transcribed table is duplicated literals — same accepted risk entityMocks.ts's own header
  already documents for its 14 ids copied from graphMocks.ts.
- `mockFetchEvidence(id)` — ~300ms delay, throws on an unmapped id (same throw/catch idiom
  as `mockFetchEntityDetail`).
- `validateEvidenceMockIntegrity()` (dev-only, same pattern as Days 38-39's checkers) flags
  a duplicate evidence_id across the two tiers, and — more usefully — flags any non-empty
  `quote` that doesn't appear verbatim in its own `email_body`. **This caught a real bug
  before it shipped**: the `evidence_1750` (superseded) fixture's quote ended in a period
  but the email body had it followed by a comma ("…targeting," vs "…targeting."), so the
  brief's required `email_body.includes(quote)` highlighting would have silently failed for
  that one fixture. Fixed by rewording the body sentence to end cleanly.

**A real pre-existing cross-file data conflict was found while transcribing this table, not
introduced today:** `evidence_2211` is entityMocks.ts's second evidence_id for claim_001
(Sally Beck `reports_to` John Lavorato), but chatMocks.ts's own citation for the identical
evidence_id is a different claim entirely (Sally Beck `works_with` Louise Kitchen, claim
`claim_8842`, with real quote text). A real evidence node belongs to exactly one claim, so
the mock can't honor both. chatMocks.ts's version was kept as authoritative (it's the only
one of the two with real quote text) and the conflict is documented in
`evidenceMocks.ts`'s header comment and asserted in this session's verification (see
below) rather than silently resolved — per CLAUDE.md §5's "ask before deciding," this is
flagged here rather than picked silently. **Not user-visible today**: `ClaimCard.tsx` only
ever links to `evidence_ids[0]`, never `[1]`, so `evidence_2211` is only reachable via
chatMocks' own citation badge today, which agrees with itself. Worth a look before Day 41
if evidence_ids beyond `[0]` ever become clickable, or if the backend's real evidence graph
is used to sanity-check these mocks.

**Components** (`src/components/evidence/`):
- `ClaimSection.tsx` — claim-type badge, status badge, subject → object as `target="_blank"`
  links to `/entities/:id` (this page is itself usually opened in a new tab already, so a
  further click here shouldn't lose that tab too), a confidence bar, valid-from/valid-to
  (`null` valid_to renders "Present", matching `ClaimCard.tsx`'s Day 39 convention).
- `EvidenceQuote.tsx` — the quote in a prominent blockquote, or the brief's specified
  fallback line when empty.
- `SourceEmail.tsx` — From/To/Date/Subject header block, then the full `email_body` in a
  `<pre className="whitespace-pre-wrap break-words font-mono">` block (wraps instead of
  causing horizontal scroll, per the brief's responsive requirement) inside its own
  `max-h-[32rem] overflow-y-auto` region. Highlighting is a plain `body.split(quote)` with
  the matched segment wrapped in `<mark>` — simple substring match per the brief, no
  char-offset math.
- `pages/EvidencePage.tsx` — loading skeleton (shadcn `Skeleton`, same as
  `EntityDetailPage.tsx`) while the mock's ~300ms delay is in flight, not-found state with a
  link to `/entities`, and the exact `window.history.length > 1 ? navigate(-1) :
  navigate('/entities')` back-link pattern the brief specifies. No `MainLayout.tsx` change
  needed — `/evidence` was never added to the full-bleed route list, so it already gets the
  standard padded/page-scroll wrapper, which is what a document-like page wants.

### Verification

Same standing constraint as every prior day: no real browser available in this environment
(Playwright needs `libnspr4`/`libnss3`, no `sudo`). Used the same ephemeral
vitest+jsdom+`@testing-library/react`/`user-event`+`jest-dom` install as Days 36-39
(`--no-save`; `package.json`/`package-lock.json` md5s confirmed byte-identical before and
after, both packages fully removed afterward). Two ephemeral test files, deleted after:

1. **Data-layer checks (10/10 passed)**: `validateEvidenceMockIntegrity()` reports 0
   problems; exactly 38 distinct evidence_ids are referenced across chatMocks.ts +
   entityMocks.ts and every one resolves via `mockFetchEvidence` with a non-empty
   subject/object/claim_type/email_body and a confidence in [0,1]; an unknown id throws;
   each of the 5 showcase fixtures independently verified against its required property
   (evidence_2210's confidence/ids/recipient-count match the brief's own example exactly;
   evidence_3390's quote is genuinely `''`; evidence_1980 has 22 lines; evidence_1750 is
   `superseded` with a non-null `valid_to`; evidence_2260 has 4 recipients); the
   evidence_2211 conflict resolves to the documented (chatMocks) side.
2. **Real DOM render checks on the actual `EvidencePage` component (6/6 passed)**, wrapped
   in a `MemoryRouter`: skeleton renders before data arrives, then claim/quote/email
   sections render with correct badge text and a 85% confidence bar; the quote appears
   exactly twice (once in the blockquote, once as a single `<mark>` inside the email body —
   confirming the highlighting logic actually fires, not just that the text is present
   somewhere); the empty-quote fixture shows the fallback line and renders zero `<mark>`
   elements; an unknown id shows "was not found" with a working link to `/entities`; the
   claim section's subject link has the correct URL-encoded `href`,
   `target="_blank"`, and `rel="noopener noreferrer"`; the superseded fixture shows the
   "Superseded" badge and its `valid_to` date instead of "Present"; the multi-recipient
   fixture's four addresses all render.

`tsc -b`, `oxlint` (clean except the same pre-existing/already-accepted warning categories
as Days 36-39 — the new `react(set-state-in-effect)` hit on `EvidencePage.tsx`'s
fetch-on-id-change effect is the identical, already-documented pattern from
`EntityDetailPage.tsx`/`ClaimsTab.tsx`/etc.), and `npm run build` all clean.

**Not done:** an actual pixel/visual check in a real browser window — same standing gap as
every prior day.

### Not done / deferred

- Real `/api/evidence/{id}` integration — Day 41 by design.
- Evidence editing/annotation — explicitly out of scope per the brief.
- Side-by-side (claim-left/email-right) layout — brief explicitly asks for the simpler
  vertical stack.
- Char-offset-based highlighting (`char_start`/`char_end`) — the brief specifies simple
  `email_body.includes(quote)` string matching instead; char_start/char_end aren't even
  carried in `src/types/evidence.ts` since nothing uses them (see that file's header
  comment for the "real field but UI doesn't need it" fields).

### Suggested commit message

```
Day 40: evidence detail page — claim/quote/source-email trust chain view,
mock evidence data layer covering every evidence_id referenced by the Day 37
chat and Day 39 entity mocks, evidence links now open in a new tab

Dev-time integrity check caught a real bug pre-ship: the superseded showcase
fixture's quote didn't match its email body verbatim (trailing punctuation),
which would have silently broken the required inline highlighting. Also
surfaces (but does not silently resolve) a pre-existing data conflict where
chatMocks.ts and entityMocks.ts disagree about what claim evidence_2211
belongs to — not user-visible today, flagged for Day 41.
```

---

## Day 41 — Backend Integration

### What was built

Every page now runs on the live FastAPI backend. No production code path imports from
`src/mocks/` any more (verified: `grep -rn "mocks/" src/ --include="*.tsx" --include="*.ts"`
returns hits only inside `src/mocks/` itself).

**New files**
- `src/lib/api.ts` — the single transport layer. One function per real endpoint, returning
  the backend's shape verbatim. Every id that goes in a URL path is `encodeURIComponent()`d
  here and *only* here; ids in React state, graph node objects and comparisons stay raw.
  Exports a typed `ApiError` with `kind: 'network' | 'timeout' | 'notfound' | 'client' |
  'server' | 'parse'` so pages branch on a discriminant instead of string-matching messages.
  All requests accept an `AbortSignal` so an unmounted page's request is dropped.
- `src/lib/graphData.ts` — composes the graph explorer's data (see the graph section below).
- `src/lib/relationshipTypes.ts` — the 8 relationship types and their directionality.
- `src/components/ApiErrorState.tsx` — one place that turns an `ApiError` into user-facing
  copy, so "backend isn't running" reads identically on every page.
- `src/types/health.ts` — mirrors `HealthResponse`.

**Pages wired:** Chat, Graph Explorer, Entities list, Entity detail (+ all three tabs),
Evidence, and a basic Health page (full dashboard is still Day 42).

### The big finding: the graph endpoint cannot return the graph the brief describes

The Day 41 brief asks for 8 relationship types with arrowheads, giving
`Sally Beck --reports_to--> John Lavorato` as the example, and says to hardcode `hops=1`.
**That edge does not exist in `/api/graph/{id}/subgraph` at any depth.**

Real Neo4j relationship types are `SUBJECT`, `OBJECT`, `SUPPORTED_BY`, `FROM_MESSAGE`,
`SENT_BY`, `SENT_TO`, `MADE_BY`, `AFFECTS`, `SUPERSEDES`, `CONFLICTS_WITH`, `PARTY`. The
five claim types (`works_with`, `reports_to`, …) are **a property on Claim nodes**, never an
edge label — a claim is `(:Person)<-[:SUBJECT]-(:Claim)-[:OBJECT]->(:Person)`. Measured live
against Sally Beck (2,244 edges):

| request | result |
|---|---|
| `depth=1&limit=200` | 201 nodes: **200 Claim nodes + 1 Person**, zero entity-to-entity edges |
| `depth=2&limit=200` | 87 nodes, 112 edges, **all `PARTY`**, zero Claim nodes |

`depth=2` is not "a bigger version of depth=1": its Cypher `LIMIT`s before it has enumerated
the claim paths, so it returns an arbitrary slice. Following the brief literally would have
produced a 200-node star of claim nodes with no relationships visible.

**Asked the user rather than deciding silently (CLAUDE.md §5). The chosen option was the
claims + subgraph hybrid**, implemented in `src/lib/graphData.ts`:

1. `/api/entities/{id}/claims` → person/org edges carrying the 5 claim types, with real
   direction, confidence and mention_count. This endpoint has **no limit param** and returns
   every claim, so the core graph is always complete.
2. `/api/graph/{id}/subgraph?depth=1` → Deal (`PARTY`) and Decision (`MADE_BY`/`AFFECTS`)
   neighbours. Claim and Message nodes are discarded; the SCREAMING_CASE types are lowercased.

Both calls run in parallel via `Promise.allSettled` and are independently fault-tolerant —
one failing still renders the other's half rather than an error screen. Node type is read off
the id prefix (`person:` / `org:` / `deal:` / `decision:`), since the claims endpoint returns
ids and names but no type.

**Neighbour caps:** 20 claim counterparts + 8 structural, ranked by best confidence then
total mention_count. Sally Beck's 247 claims would otherwise be an unreadable hairball.

### Two real graph bugs found and fixed during verification

1. **Symmetric relationships were drawn twice.** `works_with` and `negotiating_with` are
   symmetric — "A works_with B" and "B works_with A" are one fact, recorded as two claims
   from two different emails. `edgeKey()` now sorts the endpoints for symmetric types, and
   symmetric edges are emitted with sorted source/target, so the same relationship reached
   from either end produces one edge. `GraphExplorerPage` imports that same `edgeKey` — using
   a different key there would have re-split them on merge across two fetches.
2. **Up to 6 parallel edges stacked into one line.** Sally Beck and Brent Price are connected
   by six genuinely distinct claims: `works_with`, `informs` both ways, `requests_from`, and
   **`reports_to` in BOTH directions** (a real contradiction in the extracted data — good
   Day 44 conflict-review material). Drawn straight, all six land on the identical line with
   six labels at the identical midpoint. Added `computeCurvatures()` to `graphForces.ts`
   (kept there, not in the canvas, because that module is importable without a DOM so a test
   can exercise the real function): edges are bundled by **unordered** pair so an A→B and a
   B→A edge fan apart instead of bowing into each other, spread evenly across ±0.45, and a
   lone edge stays perfectly straight. The edge-label renderer now places labels at the
   **quadratic bezier midpoint** (`0.25·P0 + 0.5·C + 0.25·P2`, reading force-graph's
   `__controlPoints`) — the straight midpoint sits well off a curved line.

### Other Day 41 changes to the graph explorer

- **Hops selector removed** from `GraphControls.tsx` entirely, as the brief specified.
- **Double-click opens `/entities/:id` in a new tab** via `window.open(..., '_blank')`,
  matching Day 40's evidence-link behaviour. No GraphContext / state lifting, per the brief.
- **Arrowheads** via `linkDirectionalArrowLength`, set to 0 for the two symmetric types.
- Initial view resolves `Sally Beck` through `/api/graph/search` rather than hard-coding an
  id. `?entity=<id>` in the URL overrides it — the entity detail page's "View in Graph
  Explorer" button now passes the entity, so it lands on that profile's neighbourhood.
- `mergeSubgraph` now **mutates existing node objects in place** rather than skipping them.
  Force-graph stores `x/y/vx/vy` directly on the node objects it was handed, so replacing the
  object would drop its settled position. This lets a neighbour's estimated weight be
  upgraded to its real `mention_count` once it's expanded or arrives from a search.

### Backend response shapes that differed from the frontend types

Every mock-only field carried since Day 37 was resolved rather than left lying in the types.

| Field | Reality | Handled by |
|---|---|---|
| `CitationItem.message_date` / `message_subject` | never existed on the real model | **Removed.** The evidence drawer now fetches `GET /api/evidence/{evidence_id}` on open and reads `email_date`/`email_subject`, with a skeleton while in flight and "Source metadata unavailable." on failure. |
| `EntityListItem.claim_count` | not on the model, and un-derivable without one request per row | **Removed** from the type and from `EntityCard`. |
| `EntityDetailResponse.claim_count` / `first_seen` / `last_seen` | not on the model | **Derived** in `EntityDetailPage` from a single `/claims` call (`claim_count = response.total`, dates = min/max `valid_from`), passed to `EntityHeader` as a separate `stats` prop. Deliberately the *same* call the Claims tab renders, so the header's "N claims" and the tab's card count cannot disagree. |
| `ClaimResult.evidence_ids` | real field is `evidence: list[dict]` | Type updated to the real `evidence: EvidenceRef[]`. **See the backend gap below.** |
| `GraphEdge.claim_type` / `confidence` | never populated by the route (always null) | `graphData.ts` fills them itself from the claims data. |
| `GraphEdge.claim_count` | not a backend field at all | Now genuinely derived: the number of claims of that type collapsed into the edge. |
| `EvidenceDetailResponse.subject_id` / `object_id` | not on the model; no endpoint resolves a claim to its entity ids | `ClaimSection` renders subject/object as **plain text, not links**. |
| `EvidenceDetailResponse.status` / `valid_from` / `valid_to` | live on the Claim node; evidence.py never selects them | **Removed** — the status badge and validity range are gone from the evidence page. |
| `EvidenceDetailResponse.email_to` | model has only `email_from` | **Removed** — `SourceEmail` no longer renders a "To" row. |
| claim `status` vocabulary | real values are `current` / `superseded` / `review` (5538/15/33) — **not** Day 39's `active` | Added `current` to `CLAIM_STATUS_COLORS`; `active` kept as an alias. Without this every claim would have rendered a grey "Unknown" badge. |

Also fixed while in there: the Day 37 evidence drawer linked to `/evidence/${citation.evidence_id}`
**without** `encodeURIComponent`. Real evidence ids contain a colon, so that link would have
been malformed on every citation. Now encoded.

### Backend gaps found — flagged, not worked around (CLAUDE.md §5)

1. **`ClaimResult.evidence` is always `[]`.** `entities.py`'s claims query never selects it.
   The data exists — **all 5,586 Claim nodes have a `(:Claim)-[:SUPPORTED_BY]->(:Evidence)`
   relationship** — the Cypher simply doesn't traverse it. Consequence: the "View evidence"
   link on every claim card falls through to a message saying evidence links aren't returned
   by this endpoint. Chat citations are unaffected (`CitationItem` carries a real
   `evidence_id`), so the drawer and `/evidence/:id` work correctly.
2. **`GET /api/entities?entity_type=deal` silently returns the whole corpus.** It doesn't
   filter and doesn't error — it falls through to the unfiltered `(n:Person OR n:Organization)`
   branch and returns all 21,729 person+org entities *labelled as a Deal result*. This is
   worse than the Day 39 note predicted (which expected a 404). **The Deal and Decision
   filter chips have been removed** from the entities page; only Person and Organization
   remain. `GET /api/entities/{id}` has the same restriction, so a Deal/Decision id 404s
   there. Deals and Decisions are still reachable via `/api/graph/search` and appear in the
   graph explorer.
3. **`/api/graph/{id}/subgraph` truncation makes structural neighbours best-effort.** The
   route caps at `limit=200`, has no relationship-type filter, and returns rows in Neo4j's
   enumeration order. For Sally Beck all 200 rows are `SUBJECT`/`OBJECT`, so her 83 `PARTY`
   and 867 `AFFECTS`/`MADE_BY` edges never arrive and no Deal/Decision appears in her graph.
   For `org:enron` all 200 rows are `AFFECTS`, so 8 Decision nodes *do* appear. Not fixable
   from the frontend (the limit is already at maximum). Degrades gracefully — claim edges
   come from the unlimited `/claims` endpoint, so only the Deal/Decision garnish is affected.

### The 10-second timeout had to be split

The brief specifies a 10s timeout. Applied to `/api/chat` that makes chat **permanently
broken**: the first live call aborted client-side at 10.000s, and the server log shows the
backend had returned a correct 3-citation answer at **10.2s** — the user would have seen a
timeout error and the Gemini quota would have been spent anyway. A chat turn is a
query-understanding LLM call + 4.1s of graph/semantic retrieval + an answer-generation LLM
call (+ a third call to rewrite a follow-up). So `REQUEST_TIMEOUT_MS` stays 10s for the
read-only endpoints, and `CHAT_TIMEOUT_MS = 60_000` applies to `POST /api/chat` only.

### `/api/entities?search=` behaviour (asked for explicitly)

- **Case-insensitive: YES.** `sally beck` and `SALLY BECK` return identical results — the
  Cypher is `toLower(n.canonical_name) CONTAINS toLower($search)`.
- **Matches aliases: YES.** `Sally W. Beck` (an alias, not the canonical name) matches.
- **Does NOT match email addresses.** `sbeck` returns 0 results — emails live in `n.emails`,
  which the search clause never touches, and `/api/graph/search` explicitly excludes aliases
  containing `@`.
- Substring, not prefix or fuzzy: `beck` matches `Fernley Dyson and Sally Beck` too.

⚠️ **The alias half of that is an UNCOMMITTED working-tree change to
`backend/src/api/routes/entities.py`** (mtime 00:16, before this session started — not made
by this session; CLAUDE.md §5 was respected and no backend file was touched). At `HEAD` the
condition is only `toLower(n.canonical_name) CONTAINS toLower($search)`. **If that change is
reverted or lost, alias matching disappears.** `backend/src/api/dependencies.py` has a
similar uncommitted docstring-escaping fix.

### Mock files

Not deleted, per the brief. Each of the four now carries a header banner marking it as not
part of the production code path. They **no longer type-check** (they still populate the
mock-only fields removed above), so `src/mocks` was added to `exclude` in
`tsconfig.app.json` — Vite never bundled them anyway, since nothing reachable imports them.
Update a file to the current types before bringing it back into a build.

### Verification

Same standing constraint as every prior day: **no real browser** (Playwright needs
`libnspr4`/`libnss3`, no `sudo`). Three ephemeral test layers, all removed afterwards
(`--no-save`; `package.json`/`package-lock.json` md5s confirmed **byte-identical** before and
after):

1. **Live integration, 63/63 passed** — drove the real `src/lib/api.ts` and
   `src/lib/graphData.ts` against the running backend. Covered: health; pagination and
   type filtering; the three search-behaviour findings above; colon-bearing ids round-tripping
   through `encodeURIComponent`; server-side `claim_type` filtering; timeline ascending order;
   header-stats derivation matching the Claims tab; that the composed graph leaks no claim
   nodes, uses only the 8 UI relationship types, has no plumbing types, no self-loops, every
   edge endpoint resolving to a node in the same response, and **every claim edge's direction
   matching a real subject→object claim**; expanding a neighbour; a Deal rendering in the
   graph despite 404ing on `/api/entities/{id}`; and `ApiError.kind === 'notfound'` on 404s.
2. **Curvature geometry, 9/9 passed** — lone edge stays straight; 2 edges get opposite arcs;
   A→B and B→A share one bundle; odd bundles keep a straight middle; arcs evenly spaced and
   within `MAX_CURVATURE`; **order-independent** (a merge reshuffles the array and arcs must
   not jump); and against the real 65-edge Sally Beck graph, **no two edges in any bundle
   share an arc**.
3. **DOM tests on the real components, 20/20 passed** (vitest + jsdom + testing-library,
   `fetch` stubbed, every requested URL recorded) — only Person/Organization chips rendered;
   the correct `entity_type` param sent; search **debounced** (5 keystrokes ≤ 2 requests);
   pagination driven by the API `total`; "Backend unavailable" + Retry on a network failure
   and "Something went wrong" + Retry on a 500; ids encoded on the wire but decoded for
   display; header claim count derived from the claims call; `current` status badge
   rendering; not-found states with **no** Retry button (retrying a 404 is pointless); the
   evidence quote highlighted exactly once inside a real body with nested forwarded text;
   subject/object rendered as plain text; no "To" row; empty quote producing zero `<mark>`s;
   the drawer fetching `/api/evidence` with an encoded id, degrading to "Source metadata
   unavailable." on failure, and **not fetching at all while closed**; health counts and a
   downed service showing as Error.

**Live `/api/chat` — 3 calls total** (within the CLAUDE.md §9 budget; 1 was the timed-out
attempt that revealed the timeout bug). Confirmed on real responses:
- `session_id` echoes back and the follow-up reuses the **same** session.
- `effective_question` populated on the follow-up: *"Tell me about her role"* →
  *"What is Sally Beck's role at Enron?"*
- `clarification` non-null with real structured options (`Sally Beck` vs
  `Fernley Dyson and Sally Beck`), rendered from the structured field only, per §8.2.
- Citations carry real non-empty `evidence_id`s and quotes, and `message_date` is confirmed
  **absent** from the response.
- **Citation `index` values are NOT contiguous** — a real answer cited `[7]`, `[11]`, `[10]`.
  Day 37's `AnswerText` looks citations up *by* `citation.index` rather than by array
  position and falls back to plain text on a miss, so this works correctly. Do not "fix" it
  to index into the array.

`tsc -b` clean. `npm run build` clean (587 kB / 187 kB gzipped). `oxlint` clean apart from the
same two already-accepted categories: 3 shadcn-generated `only-export-components` and 8
`react(set-state-in-effect)` on the documented reset-then-fetch effects.

**Not done:** an actual pixel/visual check in a real browser — the standing gap. The graph
canvas in particular (arrowheads, curved edges, labels on the bezier midpoints) has been
verified geometrically and mathematically but **never seen rendered**.

### Not done / deferred

- Full health dashboard — Day 42 by design; today's page is the basic version the brief
  called optional.
- Merge audit log, conflict review queue — Days 43–44.
- Caching, request deduplication, optimistic updates — explicitly out of scope. Note that
  `EntityDetailPage` and `ClaimsTab` each fetch `/claims` independently; that duplicate call
  is deliberate under this constraint and is where caching would first pay off.
- Auth beyond the hardcoded `X-User-Clearance: 4`.

### Post-session fix: aborted StrictMode requests were showing as "Backend unavailable"

Reported (with a Network-tab trace): opening the Claims tab fired two requests — the first
canceled, the second returning a real 200 with real data — but the UI still showed "Backend
unavailable" instead of the data. `main.tsx` wraps the app in `<StrictMode>`, which
double-invokes every effect in dev (mount → cleanup → mount again) specifically to surface
missing-cleanup bugs like this one; the throwaway first mount's fetch is what gets canceled.

**Root cause, found in `src/lib/api.ts`, not in `ClaimsTab.tsx`.** Every one of the 9 rewired
call sites already had the right *intent* — `catch ((err) => { if (!isAbort(err))
setError(err) })` — and `isAbort()` itself was written correctly (`err instanceof
DOMException && err.name === 'AbortError'`). The break was one layer below, in the shared
transport: `fetchApi`/`postApi`'s `catch (err) { throw ApiError.from(err) }` ran on *every*
`fetch()` rejection, abort included. `ApiError.from()` only special-cases `TimeoutError`
explicitly; anything else — including a genuine `AbortError` — fell through to the generic
`return new ApiError('network', 'Cannot connect to the backend...')` branch. That silently
converts a harmless cancelled request into a fake "backend unreachable" error, and by the
time it reaches a page's `.catch`, `err` is an `ApiError` instance, not a `DOMException` —
so `isAbort(err)` returns `false` and the mis-wrapped abort gets `setError()`'d as real. If
that rejection lands *after* the second (successful) request's `setClaims()` — which is
exactly what the timing in a cancel-then-refetch race produces — it overwrites the correct
data with the error state. Confirmed by literally reverting the fix and re-running the
repro: the aborted request rejected with `ApiError: Cannot connect to the backend...`, the
identical string `ApiErrorState` renders as "Backend unavailable."

**Fix, at the one shared root rather than in each page** (per the standing "fix the whole
class, not the reported instance" rule — this bug was never in `ClaimsTab.tsx`; every one of
the 9 files using `isAbort()` was equally exposed). `fetchApi`/`postApi` now check for a raw
abort *before* calling `ApiError.from()` and rethrow it unwrapped:
```ts
} catch (err) {
  if (isRawAbort(err)) throw err   // keep the AbortError identity intact
  throw ApiError.from(err)
}
```
so `isAbort()` downstream sees the real `DOMException` it was always checking for. No page
component changed — the fix is entirely in `src/lib/api.ts`.

**Verified two ways**, both ephemeral (`tsx` installed `--no-save`, removed after;
`package.json`/`package-lock.json` confirmed byte-identical): a script that stubs `fetch()`
to honor `AbortSignal` and reproduces the exact StrictMode timing (abort request 1
synchronously, then fire request 2, await both) — 5/5 checks passed against the fixed code,
including "request 1 rejects with the raw AbortError, not a wrapped ApiError" and "the
page-level catch pattern does NOT set an error state for the aborted request." Re-ran the
identical script against the pre-fix code (reverted by hand, not via git — `api.ts` is a new
untracked file this phase, so `git stash` doesn't apply to it) to confirm it actually fails
without the fix: 3 of 5 checks failed, with request 1 rejecting as
`ApiError: Cannot connect to the backend...` — reproducing the reported bug exactly, then
restored the fix. `tsc -b`, `oxlint` (same 11 pre-existing/accepted warnings, nothing new),
and `npm run build` all clean afterward.

**Lesson for future days:** a `catch` block's `isAbort(err)` guard is only as good as
whatever ran before it. The bug wasn't in the code that checked for the abort — it was in a
shared helper two calls upstream that silently changed the error's type before the check
ever ran. When several independent call sites share the same defensive pattern and one
report surfaces a failure, check whether they share a common dependency before assuming the
bug is local to the reported call site.

### Suggested commit message

```
Day 41: replace all mock data with live backend integration

Add a centralised API client (src/lib/api.ts) with typed ApiError kinds,
per-request abort signals, and URL-encoding of colon-bearing entity ids at the
network boundary. Wire chat, graph, entities, entity detail, evidence and a
basic health page to the real endpoints; no production code imports src/mocks/.

The graph explorer needed a new data source: /api/graph/{id}/subgraph cannot
return an entity-to-entity edge at any depth, because claim types live on Claim
NODES, not on relationships. Compose the graph instead from
/api/entities/{id}/claims (the 5 claim types, with real direction and
confidence) plus the subgraph route's Deal/Decision neighbours. Remove the hops
selector, add arrowheads for the 6 asymmetric relationship types, and open
entity profiles in a new tab on double-click.

Fix two graph bugs found in verification: symmetric relationships were drawn
twice (works_with A->B and B->A are one fact), and up to 6 parallel edges
between one pair stacked into a single unreadable line -- now fanned out with
curvature, with edge labels moved to the bezier midpoint.

Resolve every mock-only field against the real contract rather than leaving it
in the types, and split the request timeout: 10s for read-only endpoints, 60s
for /api/chat, which measurably takes 10.2s and was aborting a fraction of a
second after the backend had already answered.
```

---

## Day 42 — Health Dashboard

### What was built

Replaced the Day 41 "basic version" `/health` page with the full control-room dashboard,
built entirely against the live `/api/health`, `/api/review-queue`, and `/api/conflicts`
endpoints — no mocks. The backend's `/api/health` route and `HealthResponse` model were
already expanded by hand before this session (a `report: Optional[dict]` field carrying
`HealthMonitor.full_health_report()`) — visible as the uncommitted working-tree diff to
`backend/src/api/models.py` and `backend/src/api/routes/health.py` present at session start.
Not modified by this session, per CLAUDE.md §5. Confirmed the shape live with
`curl http://localhost:8000/api/health | jq` before writing any types, matching the brief's
CONFIRMED shape exactly, including the 2-key (not 5-key) `confidence_distribution` on this
corpus.

**Installed:** `recharts` (the tech-stack-specified charting library), `^3.10.1`.

**Types** (`src/types/health.ts`, rewritten) — `HealthResponse.report` is now
`HealthReport | null` (was missing entirely on Day 41's basic page, which only read
`status`/`services`/`counts`). Added `HealthReport` and its six nested sections
(`graph_size`, `claim_quality`, `temporal_health`, `access_levels`, `entity_stats`,
`data_quality`) typed field-for-field against the confirmed JSON — `confidence_distribution`
and `claims_by_type` are `Record<string, number>` specifically because the backend omits
empty buckets as absent keys rather than sending them as 0. Also added `ConflictItem`/
`ConflictListResponse`/`ReviewItem`/`ReviewQueueResponse`, mirroring `models.py`'s Admin
section — only `.total` is used today, but the full item shapes are there for Days 43-44 to
build on rather than being redefined later.

**API** (`src/lib/api.ts`): added `fetchReviewQueue()` and `fetchConflicts()`. Only
`fetchReviewQueue` is actually called from the dashboard — `fetchConflicts` is exported per
the brief's Step 2 for future use, but the "Conflict Pairs" stat comes from
`report.temporal_health.conflict_pairs` (already present in the one `/api/health` call), so
the page deliberately does not make a second network call just to re-derive a number it
already has.

**Components** (`src/components/health/`, all new): `StatCard`, `ConfidenceDistributionChart`
and `ClaimsByTypeChart` (Recharts `BarChart`s, indigo `#4f46e5`, rounded bar corners),
`ServiceStatusCard`, `AttentionNeededCard`, `ClaimsByStatusCard`, `TopEntitiesTable`, and a
`formatters.ts` (`formatCount`, `formatPercent`, `scoreColorClass` — the ≥95 green / ≥85 amber
/ <85 red traffic light, shared logic in case a future stat wants the same threshold).
`ConfidenceDistributionChart` exports its bucket-sorting function (`sortedBuckets`) the same
way Day 38's `graphForces.ts` exported pure geometry logic — so a test exercises the real
sort, not a re-implementation, and it's verified never to assume a fixed 5-bucket shape.

**`pages/HealthPage.tsx`** (rewritten): fetches `/api/health` and `/api/review-queue` in
parallel on mount and on a manual "Refresh" button click (`reloadToken` pattern, same as every
other page) — **no polling/auto-refresh**, per the brief: `full_health_report()` runs several
live aggregation queries over the whole graph, and the corpus is frozen, so an interval would
only add real query load for zero benefit. The review-queue fetch is best-effort and
independent of the primary health fetch: on failure it renders "—" for Pending Review without
blocking or erroring the rest of the dashboard (only a failed `/api/health` shows the
centered error+Retry state and suppresses the whole dashboard, per the brief's explicit "do
NOT show a half-loaded dashboard" instruction). `report === null` (the lightweight check
succeeded but the full report failed backend-side) is handled per-section: `ServiceStatusCard`
still renders normally since it reads only the top-level `services` array, while every
report-dependent card/chart shows a "Detailed metrics unavailable" message instead of crashing
or showing fabricated zeros.

**Sidebar:** already had a "Health" link (added Day 36, `Waves` icon) — the brief's Step 5
assumed only 4 items existed and Health needed adding as a 5th; checked `Sidebar.tsx` and
found Health was already the 4th of 4 links. No sidebar change was needed or made.

### A real gap found and fixed: `/entities?search=<name>` didn't do anything

The brief's Top Mentioned Entities table links each name to `/entities?search=<name>`
(a fallback since the health report only carries a person's name and mention count, no entity
id). `EntitiesPage.tsx` did not read any URL query param on mount — the link would have landed
on an unfiltered entity list with an empty search box, silently not doing what it visually
promises. Fixed by reading `search` from `useSearchParams()` once on mount and using it to
initialize both `search` and `debouncedSearch` state (initializing both avoids one wasted
300ms-debounced round trip on first load). This is the one change made to a page outside
today's new health files — small and scoped to making today's own new link work, not a
broader refactor of `EntitiesPage.tsx`.

### Verification

No real browser available (same standing Playwright/`libnspr4`/`libnss3` blocker as every
prior day). Used the same ephemeral `vitest` + `jsdom` + `@testing-library/react`/`user-event`
+ `jest-dom` install as Days 36-41 (`--no-save`, fully removed after; `package.json`/
`package-lock.json` confirmed byte-identical before and after via md5sum). One test file,
19/19 checks passed against the real components with `fetch` stubbed to the CONFIRMED
`/api/health` shape (cross-checked against a live curl earlier in the session) plus a live
`/api/review-queue`/`/api/conflicts` check (33 pending review, 25 conflict pairs, matching the
report's own `temporal_health.claims_by_status.review: 33`):

- `sortedBuckets` sorts the real 2-bucket distribution descending, handles a hypothetical
  5-bucket distribution without assuming a fixed shape, and returns `[]` (never throws) on an
  empty distribution.
- Loading state renders before data arrives, then the full dashboard.
- All 6 stat cards show correctly formatted values from the real report shape: `8,595`
  (Message), `25,032` (Person+Org+Deal summed), `5,586` (Claim), `97.9 / 100` (quality score,
  with the green `text-emerald-600` class at ≥95), `95.0%` (average_confidence × 100, 1dp),
  `96.7%` (verification_rate).
- Service status renders a service's `name`/`detail` text; a down service (`status: "error"`)
  gets a red dot scoped to *that service's own row*, not any row.
- Attention Needed shows the real pending-review and conflict-pair counts, both rows are
  `<a href="/conflicts" target="_blank" rel="noopener noreferrer">`; shows "All clear" when
  both are 0; shows "—" for pending review (without blocking the rest of the page) when the
  review-queue fetch fails.
- Claims by Status shows Current/Review/Superseded with correct counts and labels.
- Top Mentioned Entities links each name to a correctly URL-encoded `/entities?search=`,
  opening in a new tab.
- `report: null` renders "Detailed metrics unavailable" (found via `getAllByText`, multiple
  sections) instead of crashing, while Service Status still renders normally.
- A failing `/api/health` shows the centered error state with a Retry button and **no**
  half-loaded dashboard (`Emails Processed` provably absent from the DOM); clicking Retry
  re-fetches and recovers into the full dashboard.
- The manual Refresh button re-fetches `/api/health` (call count asserted to increment).
- "Last updated" renders from `report.timestamp`.
- The `EntitiesPage` fix: navigating to `/entities?search=Kay%20Mann` pre-fills the search
  input with "Kay Mann" and fires the real fetch with `search=Kay...` in the query string.

`tsc -b` clean. `npm run build` clean (943 kB / 288 kB gzipped — the Recharts SVG renderer is
the main addition over Day 41's 587 kB/187 kB; not addressed, consistent with Day 38's
decision not to address `force-graph`'s bundle-size warning either). `oxlint` clean apart from
the same already-accepted warning categories from every prior day, plus two new instances of
already-documented patterns: `react(set-state-in-effect)` on `HealthPage.tsx`'s own
fetch-on-mount effect (identical shape to `EntitiesPage.tsx`/`EntityDetailPage.tsx`/etc.), and
`react(only-export-components)` on `ConfidenceDistributionChart.tsx` for exporting
`sortedBuckets` alongside the component — the same tradeoff Day 38 made exporting
`graphForces.ts`'s pure logic so a test exercises the real function instead of a copy.

**Not done:** an actual pixel/visual check in a real browser — the standing gap since Day 36.
The Recharts bar charts in particular (`ResponsiveContainer` needs a real `ResizeObserver` and
real layout to size itself) were verified via a `ResizeObserver` stub in jsdom, which confirms
the components don't crash and their surrounding DOM/text is correct, but does **not** confirm
actual pixel rendering, bar proportions, or that the charts are visually legible. This is a
real gap, not a formality — flag it first if a real browser becomes available.

### Step 6 — Evidence highlighting verification result

**Evidence highlighting: STILL BROKEN — needs fix.**

Tested directly against live data rather than by inspecting code alone: took Sally Beck's
real `/api/entities/{id}/claims` (247 claims), fetched real evidence via
`/api/evidence/{evidence_id}` for the first 8 claims that had evidence, and checked whether
`SourceEmail.tsx`'s current highlighting logic (`email_body.includes(quote)`, unchanged since
Day 40 — no whitespace normalization was ever added) would find each quote in its body.
**5 of 8 failed** the plain `includes()` check; all 8 passed when both strings were normalized
by collapsing whitespace (`quote.split(/\s+/).join(' ')` equivalent) before comparing — i.e.
the mismatch is exactly the `\n`-vs-space class of bug the brief described, not something
else. Confirms the whitespace-normalization fix mentioned in the Day 42 brief as
"may or may not have been implemented" was in fact **not** implemented — `SourceEmail.tsx`'s
`renderBody()` is unchanged from Day 40. Per the brief's explicit instruction, **not fixed
today** — documented here for a future session. The fix, when it happens, needs to normalize
both `quote` and `email_body` the same way before the `includes`/`split` call (and ideally
render highlighting against the *original* unnormalized body text, not a mangled copy, since
`SourceEmail` displays the raw body verbatim in a `<pre>`).

### Not done / deferred

- A real pixel/visual check of the charts and the whole page — standing gap, see above.
- `fetchConflicts()` is implemented in `src/lib/api.ts` per the brief but not called from any
  page today — `report.temporal_health.conflict_pairs` already covers the one number the
  dashboard needs. A dedicated `/conflicts` page (Day 44) will be the first real caller.
- Evidence highlighting fix — confirmed broken, intentionally not fixed today (Step 6).
- Trend-over-time chart, `pipeline_status` UI, dark mode — explicitly out of scope per the
  brief.

### Suggested commit message

```
Day 42: health dashboard — full control-room view of graph quality metrics

Add the nested HealthReport types (graph_size, claim_quality, temporal_health,
access_levels, entity_stats, data_quality) matching the backend's newly
expanded /api/health response, plus fetchReviewQueue/fetchConflicts. Rebuild
HealthPage as a real dashboard: 6 summary stat cards, a confidence-distribution
and claims-by-type Recharts bar chart, service status, an Attention Needed card
linking to /conflicts, claims-by-status breakdown, and a top-mentioned-entities
table -- all fetched once on load plus a manual Refresh button, no polling.
Handles report: null per-section rather than crashing or showing fake zeros.

Fix a real gap found while wiring the new page: EntitiesPage never read a
?search= query param, so the dashboard's "link to /entities?search=<name>"
fallback silently did nothing. EntitiesPage now seeds its search state from
the URL on mount.

Verify (Step 6): evidence quote highlighting is still broken on real data --
5 of 8 sampled real claims fail the plain email_body.includes(quote) check
due to whitespace/newline differences; the whitespace-normalization fix
mentioned in the Day 41 log was never actually implemented. Not fixed today,
per the brief.
```

---

## Day 43 — Merge Audit Log UI

### What was built

Replaced the `/merges` placeholder with a full merge audit log: filterable/sortable table of
all 3,315 entity merges (2,024 exact + 1,291 fuzzy) with undo on active fuzzy merges. Backend
route (`GET /api/merges`, `POST /api/merges/{merge_id}/undo`) and its models were already
built by hand before this session (uncommitted `backend/src/api/app.py`/`models.py` diffs +
new `backend/src/api/routes/merges.py`) — confirmed live via curl per CLAUDE.md §5, not
modified.

**New files:**
- `src/types/merge.ts` — `MergeItem`/`MergeListResponse`/`MergeUndoResponse`, mirroring the
  confirmed backend shape.
- `src/lib/mergeTypes.ts` — strategy/phase/status badge colors and labels, same pattern as
  `entityTypes.ts`/`claimTypes.ts`.
- `src/components/merges/MergeFilterBar.tsx` — phase/status segmented controls, a native
  `<select>` strategy dropdown, and a client-side search input.
- `src/components/merges/MergeTable.tsx` — sortable columns (click a header to toggle
  asc/desc), strategy/phase/status pills, Undo button gated on `merge.undoable`.
- `src/components/merges/UndoMergeDialog.tsx` — confirmation dialog using the newly-installed
  shadcn `alert-dialog` (`npx shadcn add alert-dialog`; built on the already-installed
  `@base-ui/react/alert-dialog`, no new npm dependency — `package.json`/`package-lock.json`
  unchanged).
- `src/pages/MergesPage.tsx` (rewritten) — orchestrator: fetches on phase/status/strategy
  change (server-side params) and after a successful undo; search and sort are client-side
  over the loaded page. Dismissible success/error banner (no toast library added — none
  exists in this app yet, and adding one wasn't in scope). No pagination, per the brief —
  3,315 rows client-rendered in one table.

**Small additive edits:**
- `src/components/layout/Sidebar.tsx` — added "Merges" (lucide `GitMerge` icon) as the 5th
  nav item, after Health.
- `src/components/health/AttentionNeededCard.tsx` — added a persistent "View Merge Audit
  Log →" link (opens `/merges` in a new tab), so the health dashboard has a direct path to
  the audit log in addition to the sidebar.
- `src/lib/api.ts` — added `fetchMerges()`/`undoMerge()`, plus a real cross-cutting fix (see
  below).

### Spec-vs-backend mismatch: strategy vocabulary

The brief lists the fuzzy-strategy dropdown as `email_match, normalized_name_match,
middle_initial, nickname, domain_match`. **Verified live against `GET /api/merges` that this
is wrong**: the backend has zero merges with strategy `middle_initial`, and the domain-based
strategy is actually spelled `same_domain`, not `domain_match`. Real observed strategies,
confirmed with a `curl | jq` breakdown by phase:
- exact phase → `email_match` (1,262), `normalized_name_match` (762)
- fuzzy phase → `fuzzy` (792), `same_domain` (296), `nickname` (203)

The strategy dropdown (`MergeFilterBar.tsx`) is hardcoded to these 5 real values, not the
brief's list — using the brief's spelling would have made the "Same Domain" filter silently
return zero rows forever. `mergeTypes.ts` keeps label/color entries for `domain_match` and
`middle_initial` too, in case a future resolution run ever produces them.

### Real gap found and fixed: the shared API client discarded the backend's actual error text

The brief's undo-error requirement ("show the error message from the API") exposed a
pre-existing, general gap in `src/lib/api.ts` dating to Day 41: `errorForStatus()` only ever
returned a generic per-status-code string ("Request rejected by the backend (HTTP 400).")
and never looked at the response body, even though every FastAPI `HTTPException` sends a
real `{"detail": "..."}` message (e.g. the undo route's "Merge {id} is already undone" / "not
found"). This wasn't unique to merges — `ChatPage.tsx`'s `chatErrorMessage()` and
`ApiErrorState.tsx` would have shown the same generic text for any 4xx/5xx on any endpoint.

Fixed at the shared root rather than only for the undo call (per the standing "fix the whole
class" rule): both `fetchApi` and `postApi` now call a new `detailFromResponse()` before
constructing the `ApiError`, which reads the JSON body's `detail` field when present and
falls back to the original generic text otherwise — so no existing page's copy changes
unless the backend actually sent a `detail` string. Verified with an ephemeral
vitest+jsdom test (stubbed a 400 with `{"detail": "Merge fuzzy-001 is already undone"}`):
the undo banner shows that exact string, not "Request rejected by the backend...". This is
an unrequested but narrowly-scoped, backward-compatible fix to shared infrastructure — flagged
here explicitly rather than silently bundled in, per CLAUDE.md §5.

### Verification

No real browser available (same standing Playwright/`libnspr4`/`libnss3` blocker as every
prior day). Used the same ephemeral `vitest`+`jsdom`+`@testing-library/react`/`user-event`+
`jest-dom` install as every prior day (`--no-save`; `package.json`/`package-lock.json`
confirmed byte-identical via md5sum before and after, both installs fully removed
afterward). Two ephemeral test files, deleted after:

1. **`MergesPage`, 9/9 passed**: initial load renders all 5 fixture rows with the correct
   "N exact + M fuzzy" subtitle; Undo buttons appear only on active+undoable fuzzy rows (2 of
   5); phase/status/strategy filters each re-fetch with the correct query param and narrow
   the table; the search box filters client-side with **no additional fetch call**; clicking
   Undo opens the dialog with the correct source/target names substituted in; confirming
   calls the undo endpoint exactly once, closes the dialog, shows the API's success message,
   and re-fetches the table; cancelling calls the undo endpoint zero times; clicking a column
   header sorts ascending then descending; an unmatched search shows "No merges match your
   filters."
2. **Undo error handling, 1/1 passed**: the detail-parsing fix above, in isolation.

**Never called the real undo endpoint** — the session brief explicitly says not to actually
undo any merges today; all verification used a stubbed `fetch`. Confirmed via a `curl -X
POST` to a nonexistent merge id (`404`, doesn't touch real data) that the route exists and
returns JSON, without touching any real merge record.

`tsc -b` clean. `npm run build` clean (957 kB / 292 kB gzipped — the alert-dialog primitive
added negligible size; the >500KB warning is the same pre-existing note from Days 38/42, not
addressed here for the same reason). `oxlint` clean apart from the same already-accepted
warning categories from every prior day, plus one new instance of the already-documented
`react(set-state-in-effect)` pattern on `MergesPage.tsx`'s own reset-then-fetch effect
(identical shape to `EntitiesPage.tsx`/`HealthPage.tsx`/etc.).

**Not done:** an actual pixel/visual check in a real browser — the standing gap since Day 36.

### Not done / deferred

- Actually undoing a merge against the live backend — deferred to manual verification outside
  this session, per the brief.
- Server-side pagination — explicitly out of scope; all 3,315 rows render client-side.
- A toast notification library — the success/error banner is a plain dismissible inline
  element instead, since no toast primitive exists anywhere in this app yet and adding one
  wasn't asked for.
- CLAUDE.md's new "Deferred Decisions" section (Step 7 of the brief) was added at the end of
  the file.

### Post-session fix: search box input lag (measured, root cause was NOT the filtering)

Reported: typing in the merge audit log's search box lagged badly, with the suspicion that
"filtering runs synchronously on every keystroke against the full ~3,315-row dataset with no
debouncing."

**Measured before assuming.** Built an ephemeral vitest+jsdom harness that generated 3,315
rows in the real 2,024-exact/1,291-fuzzy split, mounted the real `MergesPage`, wrapped it in a
React `<Profiler>`, and timed each keystroke. jsdom is slower than a real browser in absolute
terms, so only ratios and before/after deltas are meaningful — but they were unambiguous:

| measurement (before) | result |
|---|---|
| filter + sort over all 3,315 rows | **3.3 ms per keystroke** |
| one full render of the 3,315-row table | **1,869 ms** |
| typing "sally" (5 chars) | **2,752 ms total**, per-keystroke `[1923, 466, 165, 112, 86]` ms |
| React commit for the last keystroke | **60.6 ms** |

**The filtering was never the problem — it was ~0.1% of the cost.** The giveaway is the
per-keystroke shape: it *falls* from 1,923 ms to 86 ms as the query gets longer. Filtering
work is constant (it always scans all 3,315 rows regardless of query length), so a
filtering-bound cost would have been flat. What actually falls as the query narrows is the
number of `<tr>`s React has to reconcile and jsdom has to mutate. The cost tracked rows
rendered, not characters filtered.

**Root cause:** `MergeTable` renders one row per merge — up to 3,315 rows × 8 cells, 3 badge
pills each, plus a Button with an icon on all 1,291 fuzzy rows — and it is neither paginated
nor virtualised (the Day 43 brief explicitly forbade pagination). Every keystroke called
`setSearch`, which recomputed `visibleMerges` and re-rendered that entire table
**synchronously**. Because the search box is a *controlled* input (`value={search}`), the
browser cannot paint the typed character until that render commits — so the multi-hundred-
millisecond table render landed as lag on the input itself, which is exactly what was felt.

**Fix — three parts, all necessary:**
1. **Debounce (250 ms).** `search` (drives the input) is now separate from `debouncedSearch`
   (drives the filtering), with the standard `useEffect` timer, same pattern as
   `EntitiesPage.tsx`'s 300 ms server-side search. Turns one expensive render per keystroke
   into one per typing pause.
2. **`React.memo` on `MergeTable`.** *The debounce alone would not have fixed this.* Every
   keystroke still re-renders `MergesPage`, and React re-renders children regardless of
   whether their props changed — so the table would still have reconciled all 3,315 rows per
   keystroke, just with identical data. memo() is what actually stops the work.
3. **Referentially stable props**, without which memo() is a no-op: `sortKey`/`sortDir` were
   merged into a single `sort` state object so `handleSort` could become a dependency-free
   `useCallback` (two separate setState calls would have needed the current key in scope,
   making the handler a new function every render); `visibleMerges` is memoised on
   `debouncedSearch` rather than `search`; `onUndoClick` was already a stable state setter.

Also extracted the filter+sort into **`src/lib/mergeFilter.ts`** (`filterAndSortMerges`), so a
test exercises the real function rather than a copy — the same reason Day 38 exported
`graphForces.ts` and Day 42 exported `sortedBuckets`. While there, it re-uses one
`Intl.Collator` instead of calling `localeCompare` per comparison, and parses each timestamp
once (decorate–sort–undecorate) instead of ~2n·log n times inside the comparator. That's
tidiness, not the fix — it was already only 3 ms.

**After, same harness, same machine:**

| measurement (after) | before → after |
|---|---|
| typing "sally" (5 chars) | 2,752 ms → **98.8 ms** (~28× faster) |
| per-keystroke | `[1923, 466, 165, 112, 86]` → `[55, 17, 10, 9, 9]` ms |
| React commit per keystroke | 60.6 ms → **1.9 ms** (~32× less work) |
| debounce flush | one single commit of 389.7 ms, once the user pauses |

The 1.9 ms per-keystroke commit is the proof the table is no longer re-rendering while
typing — that figure is just the filter bar's own input update. (One caveat on reading these
numbers: the harness's "debounce flush wall time" of ~7 s is a testing-library polling
artifact from re-querying a multi-thousand-row jsdom DOM, **not** a user-visible delay; the
389.7 ms commit is the real figure. The "full table render" measurement also drifted between
runs, 1,869 ms vs 2,816 ms, from machine noise on an identical code path — memo() does not
affect a cold mount.)

**Verified, 11/11 passed** (ephemeral vitest+jsdom, removed after; `package.json`/
`package-lock.json` md5s confirmed byte-identical): `filterAndSortMerges` filters on either
entity name case-insensitively, handles whitespace-only and no-match queries, **produces
byte-identical ordering to the previous `localeCompare`/`new Date()` implementation** for
name, timestamp and confidence sorts (so the collator swap changed speed, not behaviour), and
does not mutate its input; the input reads `"enron"` immediately after typing while the table
still shows all 5 rows, then catches up after the debounce; a fast burst of keystrokes filters
**once**, never on intermediate prefixes; and every Day 43 behaviour still works — phase/
status/strategy server-side refetches, column sort toggling, the undo dialog and its success
banner, the empty state, and a search typed while a filter refetch is in flight surviving that
refetch ("Showing 1 of 3 merges"). `tsc -b`, `npm run build` and `oxlint` all clean, with the
oxlint warning count unchanged at 13 (the debounce timer is inside a `setTimeout` callback, so
it adds no new `set-state-in-effect` warning).

**Known remaining limitation, not fixed:** the fix removes the *per-keystroke* cost, but the
one render that happens after the pause still reconciles the whole filtered result set —
389.7 ms in jsdom for 415 rows. Clearing the search box back to all 3,315 rows is still the
single most expensive interaction on the page. The real remedy is pagination or row
virtualisation, which the Day 43 brief explicitly deferred ("3,315 rows is manageable for a
portfolio demo... don't pre-optimize"). Flagging it here rather than deciding unilaterally.

### Suggested commit message

```
Day 43: merge audit log UI — filterable/sortable table of all 3,315 entity
merges (2,024 exact + 1,291 fuzzy), confirmation dialog + undo for active
fuzzy merges, sidebar entry and a health-dashboard link

Hardcode the strategy filter to the real 5 values confirmed live against
GET /api/merges (email_match, normalized_name_match, fuzzy, nickname,
same_domain) rather than the brief's list, which names a nonexistent
"middle_initial" strategy and misspells "same_domain" as "domain_match".

Fix a real Day-41-era gap in src/lib/api.ts: fetchApi/postApi discarded
every backend HTTPException's actual `detail` message in favor of a
generic "HTTP 400" string. Both now surface the real detail text when
present, falling back to the old generic copy otherwise -- fixes the
undo dialog's error message and every other endpoint's error handling
at the same time.

Add CLAUDE.md's "Deferred Decisions" section per the Day 43 brief.

Fix search box input lag, measured rather than assumed: the filtering was
never the bottleneck (3.3ms over all 3,315 rows). The cost was re-rendering
the un-virtualised 3,315-row table synchronously on every keystroke, which
blocked the controlled input from painting the typed character. Debounce
the search at 250ms, memo() the table, and make its props referentially
stable (single sort-state object + useCallback) so memo actually applies --
without the memo the debounce alone would still have reconciled every row
per keystroke. Typing 5 characters: 2,752ms -> 98.8ms; per-keystroke React
commit 60.6ms -> 1.9ms.

Extract the filter/sort into src/lib/mergeFilter.ts so tests exercise the
real function, reusing one Intl.Collator and parsing each timestamp once;
verified to produce ordering identical to the previous implementation.
```

---

## Day 44 — Conflict Review Queue

### What was built

Replaced the `/conflicts` placeholder with a full conflict review queue: one card per grouped
conflict (2–4 contradicting `reports_to` claims sharing a subject), a claims comparison table
with shared-date highlighting, and three resolution actions (Keep Best / All Historical /
Dismiss). Backend routes (`GET /api/conflict-groups`, `POST
/api/conflict-groups/{conflict_id}/resolve`) and their models were already built by hand
before this session (uncommitted `backend/src/api/models.py`/`routes/admin.py` diffs) —
confirmed live via `curl http://localhost:8000/api/conflict-groups`, matching the brief's
CONFIRMED shape exactly (14 conflicts, all `classification: "direct_contradiction"`, all
`resolution: "needs_review"`, claim counts per group `[4, 3, 3, 3, 2×10]`). Not modified by
this session, per CLAUDE.md §5.

**New files:**
- `src/types/conflict.ts` — `ConflictClaimDetail`/`ConflictGroup`/`ConflictGroupListResponse`/
  `ConflictResolveRequest`/`ConflictResolveResponse`, mirroring the confirmed backend shape.
  Kept separate from `src/types/health.ts`'s existing `ConflictItem`/`ConflictListResponse`
  (Day 42, the older flat `/api/conflicts` endpoint returning individual claim pairs) — the two
  endpoints return genuinely different shapes and neither was touched by the other.
- `src/lib/conflictTypes.ts` — classification/resolution badge colors and labels, same
  lookup-map-plus-fallback pattern as `entityTypes.ts`/`claimTypes.ts`/`mergeTypes.ts`. Includes
  a `bg-red-100 text-red-700` entry for `direct_contradiction` (a color not used anywhere else
  in the app) and an `undated` entry the live corpus never actually produces today but the
  backend model supports.
- `src/lib/conflictFilter.ts` — three pure functions extracted so a test exercises the real
  logic, same reasoning as Day 38's `graphForces.ts`/Day 42's `sortedBuckets`/Day 43's
  `mergeFilter.ts`: `filterConflicts` (status + case-insensitive subject-name search),
  `sharedDates` (which `valid_from` values are shared by 2+ claims in one group — the core
  visual contradiction signal a null `valid_from` never counts as shared with another null),
  and `bestClaim` (highest-`mention_count` claim, the Keep Best dialog's default selection).
- `src/components/conflicts/ConflictFilterBar.tsx` — status segmented control (All / Needs
  Review / Resolved / Dismissed) + debounced search input. Same local, unexported
  `SegmentedControl` shape as `MergeFilterBar.tsx`, kept as its own copy per that file's
  precedent rather than extracted to a shared component.
- `src/components/conflicts/ConflictCard.tsx` — one card per conflict group: header (subject
  name, claim-type/classification/resolution badges, reason text), a claims comparison table
  (Reports To / Date / Confidence / Mentions), and — only when `resolution === "needs_review"`
  — the three action buttons.
- `src/components/conflicts/KeepBestDialog.tsx` — radio-option dialog (plain native
  `<input type="radio">`s styled with Tailwind's `has-[:checked]` variant, not a new shadcn
  primitive — no npm dependency needed beyond what Day 36 already installed), defaulting to
  `bestClaim()`'s pick, re-seeded via an effect whenever a different conflict opens it.
- `src/components/conflicts/ConfirmResolveDialog.tsx` — shared by "All Historical" and
  "Dismiss" (both are a single confirm with no extra input, differing only in copy and which
  action they submit); "Keep Best" needed its own dialog because it collects a winning claim
  first.
- `src/pages/ConflictsPage.tsx` (rewritten from the placeholder) — orchestrator: fetches once on
  mount and again only after a resolution action (`reloadToken`, same pattern as every other
  page) or Retry, no auto-polling. Debounced client-side status + search filtering via
  `filterConflicts`. Dismissible success/error banner, identical inline pattern to
  `MergesPage.tsx`'s (no toast library exists in this app, unchanged from Day 43's decision).

**Small additive edit:** `src/components/layout/Sidebar.tsx` — added "Conflicts" (lucide
`AlertTriangle` icon) as the 6th nav item, after Merges, per the brief. The Health dashboard's
"Conflict Pairs" link already pointed at `/conflicts` since Day 42 (added alongside "Pending
Review" in `AttentionNeededCard.tsx`) — nothing needed there. Added a small note in this page's
own footer explaining the expected count mismatch (Health's 25 "Conflict Pairs" counts
individual contradicting claim pairs; this page's 14 groups those pairs by subject +
relationship type) rather than touching the health page.

**`src/lib/api.ts`:** added `fetchConflictGroups()`/`resolveConflict()`, plus their types
imported from the new `src/types/conflict.ts`.

### A deliberate deviation from the brief's suggested fallback link

The brief's suggested entity link was `/entities?search=<name>`, "as a fallback if you don't
have the entity ID in the right format for a direct link." Checked the confirmed response
shape first: every claim's `object_id` (e.g.
`person:beck-sally:sally-beck-at-enron-com`, `org:office-of-the-chairman`) is already a real
entity id in the exact format every other route in this app expects. Since `reports_to`'s
object is always a Person or Organization — both reachable via `GET /api/entities/{id}` per the
Day 39 gotcha about that route's Person/Organization-only restriction — the "Reports To" cells
link directly to `/entities/${encodeURIComponent(object_id)}` instead of falling back to a
name-based search. More precise than the brief's suggested fallback (a name search can hit
zero or multiple results; a direct id link cannot), and avoids the double round-trip a search
page would need. Documented here since it's a deviation from what the brief explicitly wrote,
even though it's a strictly better version of the same intent.

### Verification

No real browser available (same standing Playwright/`libnspr4`/`libnss3` blocker as every prior
day). Same ephemeral `vitest`+`jsdom`+`@testing-library/react`/`user-event`+`jest-dom` install as
every prior day (`--no-save`; `package.json`/`package-lock.json` confirmed byte-identical via
md5sum before and after; all ephemeral files deleted afterward). One test file, **18/18 passed**,
run against the real components with `fetch` stubbed to the **actual live response** saved via
`curl` earlier in the session (not a hand-typed fixture) — 14 real conflicts, real ids, real
dates:

- All 14 cards render with the correct subject headings, subtitle counts
  ("14 unresolved, 0 resolved"), and per-card badges (claim type, classification, resolution).
- `sharedDates`/`filterConflicts`/`bestClaim` unit-tested directly against the real fixture data
  — confirmed the real Brent Price group's two shared-date pairs (`2000-03-21` ×2,
  `2000-08-16` ×2) are exactly what gets amber-highlighted (4 of 4 cells), that `bestClaim`
  picks Sally Beck's claim (7 mentions, the group's highest) as the Keep Best default, and that
  a null `valid_from` never counts as shared with another null.
- Status filter narrows correctly (filtering to "Resolved" or "Dismissed" currently always
  empties the list, since every live conflict is still `needs_review` — expected, not a bug).
- Search is debounced: typing "Brent" leaves all 14 cards rendered until the debounce timer
  fires, then narrows to 1.
- "Keep Best" opens with the correct claim pre-selected, and confirming posts
  `{action: "keep_one", winning_claim_id: "claim:fea48cdd3aec454d"}` to
  `/api/conflict-groups/conflict%3Ae40c373b716b/resolve` (URL-encoded conflict id verified), then
  shows the real success-message shape and closes the dialog.
- "All Historical" and "Dismiss" each open their own confirm dialog with the brief's exact
  required copy and post the correct action string.
- A resolved conflict (`resolution: "resolved"`, `current_claim_id` set) hides all three action
  buttons and shows a "✓ Current" badge on the winning claim's row.
- "Reports To" links resolve to `/entities/person%3Abeck-sally%3Asally-beck-at-enron-com`
  (URL-encoded `object_id`) with `target="_blank"` and `rel="noopener noreferrer"`.
- A network failure renders "Backend unavailable" + Retry, and Retry recovers into the full
  card list.
- An unmatched search shows "No conflicts match your filters."

`tsc -b` clean. `npm run build` clean (968 kB / 295 kB gzipped — the >500KB warning is the same
pre-existing note from Days 38/42/43, not addressed here for the same reason). `oxlint` clean
apart from the same already-accepted warning categories from every prior day, plus two new
instances of the already-documented `react(set-state-in-effect)` pattern:
`ConflictsPage.tsx`'s own reset-then-fetch effect, and `KeepBestDialog.tsx`'s re-seed-selection-
on-prop-change effect (same shape as `UndoMergeDialog`-adjacent patterns elsewhere).

**Not done:** an actual pixel/visual check in a real browser — the standing gap since Day 36.
**Also not exercised today:** the "Resolved"/"Dismissed" filter states and the winning-claim
"✓ Current" badge were only verified against a hand-modified copy of the real fixture (see
above) — the live corpus has zero resolved/dismissed conflicts today, since the brief
explicitly says not to actually resolve any conflicts this session.

### Not done / deferred

- Actually resolving any conflict against the live backend — deferred per the brief; every
  verification call used a stubbed `fetch`. The real `POST` route was never hit.
- Server-side pagination — not needed at 14 rows.
- A toast library — inline dismissible banner, same as Day 43.
- Editing/adding a human note (`ConflictResolveRequest.note`) in the UI — the brief's request
  body shows an optional `note` field but never asks for UI to set it, so `resolveConflict()`
  accepts it as an optional parameter but no dialog collects one today.

### Suggested commit message

```
Day 44: conflict review queue — grouped conflict cards with claims
comparison table, shared-date highlighting, and Keep Best / All
Historical / Dismiss resolution actions against the new
/api/conflict-groups endpoints

Link each "Reports To" claim directly to /entities/{object_id} rather
than the brief's suggested name-search fallback -- the confirmed
response shape already carries a real entity id in the format every
other route expects, since reports_to's object is always a Person or
Organization (both reachable via GET /api/entities/{id}).

Add sidebar entry (AlertTriangle icon) after Merges. The health
dashboard's "Conflict Pairs" link already pointed at /conflicts since
Day 42; add a footer note on this page explaining why its count (14
grouped conflicts) differs from that one (25 individual claim pairs).

Verify 18/18 against the real live /api/conflict-groups response
(not a hand-typed fixture) with fetch stubbed: card rendering, shared-
date highlighting matches the real Brent Price group's two date
pairs, Keep Best defaults to the real highest-mention_count claim and
posts the correct claim id, All Historical/Dismiss post the correct
action, resolved-state badge, direct entity links, debounced search,
status filtering, and error/retry.
```

### Post-session addition: subject_aliases + per-claim evidence fields

Same-day follow-up, after the backend response gained three new fields the initial build
didn't have: `subject_aliases: string[]` on each conflict group, and `evidence_id: string |
null` + `evidence_count: number` on each claim. Confirmed live via curl before touching any
code (same standing habit this whole session) — all 14 live claims currently have a non-null
`evidence_id` with `evidence_count === mention_count`, so the null-evidence and
evidence-count-vs-mention-count-mismatch cases were exercised with a hand-modified copy of the
real fixture rather than live data.

**Changes:**
- `src/types/conflict.ts` — added the three fields to `ConflictGroup`/`ConflictClaimDetail`.
- `src/lib/conflictFilter.ts` — `filterConflicts` now also matches the search query against any
  string in `subject_aliases`, not just `subject_name`, so searching e.g. "Jim Steffes" finds
  the "James Steffes" conflict group.
- `src/components/conflicts/ConflictCard.tsx`:
  - The subject name (previously plain bold text in the card header) is now a link to
    `/entities/{subject_id}`, same styling and new-tab behavior as the existing object-name
    links — `subject_id` is the same kind of real entity id `object_id` already was.
  - Each claim's Mentions cell gained a small `FileText` icon-link (`aria-label`/`title="View
    evidence"`) to `/evidence/{evidence_id}`, shown only when `evidence_id` is non-null, plus a
    `+N more` note (`evidence_count - 1`) when `evidence_count > 1`.

No other files changed — the resolution actions, filter bar, dialogs, and shared-date
highlighting are untouched.

**Verification:** same ephemeral vitest+jsdom pattern as every prior day (`--no-save`, fully
removed after; `package.json`/`package-lock.json` confirmed byte-identical). 7/7 new checks
passed against the refreshed live fixture: `filterConflicts` matches "Jim Steffes" to the James
Steffes group and still matches direct subject-name search; the subject name renders as a link
to the correct URL-encoded `subject_id` with `target="_blank"`; a claim's "View evidence" link
resolves to the correct URL-encoded `evidence_id`; `evidence_count > 1` shows "+N more" (and
`evidence_count === 1` shows none); a null `evidence_id` renders no link on that claim's row;
and typing an alias into the live search box narrows to the one matching card. `tsc -b`,
`oxlint` (same categories as before, no new ones), and `npm run build` all clean.

### Suggested commit message (follow-up)

```
Day 44 follow-up: wire subject_aliases and per-claim evidence fields
into the conflict review queue

Subject name is now a link to /entities/{subject_id}, matching the
existing object-name link style. Each claim's Mentions cell gains a
"View evidence" icon-link to /evidence/{evidence_id} (only when
non-null) and a "+N more" note when evidence_count > 1. Search now
matches subject_aliases as well as subject_name.
```

### Discussion: how "one evidence link per claim" is decided, and a real asymmetry between the two pages that show it (not fixed, backlog only)

The user asked, after seeing the Conflicts page's evidence icon + "+N more" note, how the single
linked evidence record gets chosen out of all the evidence backing a claim — and whether the
entity profile page's Claims tab does the same thing. Investigated both backend routes (read-only,
no backend files touched, per CLAUDE.md §5) rather than answering from memory, since an earlier
session's log entry (Day 41) turned out to be stale.

**Both pages pick "the evidence with the highest `confidence`", but that framing is close to
meaningless in practice:**

- `backend/src/api/routes/admin.py` (conflict-groups, lines ~186-191):
  `ORDER BY e.confidence DESC`, takes `evidence_ids[0]` as `evidence_id`, and separately returns
  `evidence_count` as the TRUE total via `size(evidence_ids)` — not capped.
- `backend/src/api/routes/entities.py` (entity claims, lines ~317-329): same
  `ORDER BY e.confidence DESC`, but `LIMIT 5` — fetches up to 5 evidence records per claim.
  `src/components/entity/ClaimCard.tsx`'s `claim.evidence.find((e) => e.evidence_id)` then
  takes the first of those 5 as the one it links to; **the other up-to-4 fetched records are
  discarded** — no "+N more", no count, nothing shown for them today. This is real, unused
  data already coming back over the wire on every entity page load.
- **Neither Cypher query has a secondary sort key.** Checked live rather than assumed: all 5
  evidence records backing one real Sally Beck claim (`claim:db051bf9828fe9f0`) have
  `confidence: 1.0` — confirmed via `GET /api/evidence/{id}` on each. Confidence in this corpus
  reads as a flat extraction-time default rather than a computed score, so ties are the norm,
  not an edge case. With everything tied, `ORDER BY e.confidence DESC` doesn't select anything
  — the "winner" is whatever order Neo4j's storage/scan happens to return tied rows in, which
  Cypher does not guarantee to be stable across query-plan changes, Neo4j versions, or re-runs.
  So "which evidence gets linked" is, for most claims today, effectively incidental rather than
  a deliberate choice.

**User's decision this session: leave all of this exactly as it is for now.** Nothing below was
implemented — recorded purely as a backlog list for whenever this area gets revisited (Week 8
debugging pass is the natural home, per the existing "chatbot needs a dedicated debugging pass"
backlog item in CLAUDE.md's Deferred Decisions):

1. Neither Cypher query has a real tiebreaker. If ordering is ever meant to mean something (most
   recent, most specific quote, etc.), both `admin.py`'s and `entities.py`'s `ORDER BY e.confidence
   DESC` need a second sort key — a one-line change in each, but a backend change (CLAUDE.md §5,
   the user's call, not this session's).
2. The entity Claims tab already fetches up to 5 evidence records per claim but only surfaces one
   — no "+N more" indicator despite having the data. Could get the same treatment
   `ConflictCard.tsx` has today, purely on the frontend (no backend change needed — the data's
   already in the response).
3. The entity page's cap of 5 means its "how many pieces of evidence exist" is unknowable from
   that response alone once a claim has more than 5 — unlike the Conflicts page, whose
   `evidence_count` is a true, uncapped DB count. If a "+N more" ever gets added to the entity
   page (item 2), its count would need a real `evidence_count`-style field from the backend
   rather than `evidence.length`, or it will silently under-report for any claim backed by more
   than 5 sources.

### Post-session addition: split Mentions and Evidence into separate columns

Same-day follow-up, requested after seeing the combined column live: the Mentions column was
showing the mention count, the evidence icon-link, and the "+N more" note all stacked together.
The user asked for `ConflictCard.tsx`'s claims table to have a dedicated **Evidence** column
(the icon link + note), separate from **Mentions** (just the number) — and for the note's wording
to read "+N more evidence sources" instead of the terser "+N more".

**Change, `src/components/conflicts/ConflictCard.tsx` only:**
- Table header gained a 5th column: Reports To / Date / Confidence / Mentions / Evidence.
- The Mentions cell is now just `{c.mention_count}` — no icon, no note.
- The new Evidence cell holds the `FileText` icon-link to `/evidence/{evidence_id}` (unchanged
  behavior: shown only when `evidence_id` is non-null) plus, when `evidence_count > 1`, "+N more
  evidence sources" (`evidence_count - 1`, same math as before — just reworded). A claim with a
  null `evidence_id` now shows a plain "—" in that column instead of an empty cell.

No other files changed — types, filtering, dialogs, and resolution actions are untouched.

**Verification:** same ephemeral vitest+jsdom pattern as every prior change this session
(`--no-save`, fully removed after; `package.json`/`package-lock.json` confirmed byte-identical).
5/5 checks passed against the live `/api/conflict-groups` response: header has distinct
"Mentions" and "Evidence" `columnheader`s; the Mentions cell contains only the plain number with
no link inside it; the Evidence cell's link resolves to the correct URL-encoded `evidence_id` and
shows the exact "+N more evidence sources" text for Sally Beck's claim (`evidence_count: 7` →
"+6 more evidence sources"); a claim with `evidence_count === 1` shows the icon with no "more"
text; and a null `evidence_id` renders "—" with no link. `tsc -b`, `oxlint` (same categories as
before, no new ones), and `npm run build` all clean.

### Suggested commit message (follow-up)

```
Day 44 follow-up: split Mentions and Evidence into separate columns
on the conflict review queue's claims table

Mentions now shows only the plain count. New Evidence column holds
the "View evidence" icon-link and, when evidence_count > 1, a
"+N more evidence sources" note (reworded from "+N more"). A null
evidence_id now renders "—" instead of an empty cell.
```

### Post-session addition: Auto-Resolved tab for temporal-succession conflicts

Same-day follow-up: a new read-only backend endpoint, `GET /api/conflict-resolutions`, returns
13 conflicts the system resolved on its own by ordering claims chronologically (no human review
needed) — distinct from `/api/conflict-groups`'s 14 `needs_review` conflicts. Confirmed the
shape live before writing anything, and specifically checked (not assumed) three claims the
brief made about the data: `claims` arrives already sorted ascending by `valid_from` on all 13
groups, `current_claim_id` always matches the *last* claim in that sorted array, and
`superseded_claim_ids` always equals exactly "every other claim's id" — all held with zero
exceptions across the live corpus.

**New files:**
- `src/components/conflicts/shared.tsx` — extracted `Pill` and a renamed `formatConflictDate`
  out of `ConflictCard.tsx` (previously private, unexported helpers there) so the new
  `AutoResolvedCard.tsx` doesn't duplicate the date parser's timezone-safety logic (parsing
  "YYYY-MM-DD" as local calendar components rather than `new Date(str)`, which drifts a day
  under negative UTC offsets). `ConflictCard.tsx` now imports both from here instead of
  defining its own copies — pure extraction, no behavior change (re-verified with a regression
  test, see below).
- `src/components/conflicts/AutoResolvedCard.tsx` — read-only card, no props for action
  handlers (there is nothing to act on). Header: subject name linked to
  `/entities/{subject_id}` (same style as the review cards), "Temporal Succession"
  (teal) + "Auto-Resolved" (green) badges, reason text. Body: a vertical timeline reusing the
  same `border-l` + dot visual language as `src/components/entity/TimelineTab.tsx` (chosen over
  a horizontal arrow chain specifically for consistency with that existing pattern, both are
  literally "sorted claims for one subject over time"), oldest claim at top since the backend
  already sorts ascending. Each entry: object name linked (dimmed + `line-through` when
  superseded, full-opacity `text-primary` when current), the date, and a "Superseded"/"Current"
  pill (green dot + `CheckCircle2` check for current, reusing the exact "✓ Current" pattern
  `ConflictCard.tsx` already uses for a `keep_one` winner).

**Changed:**
- `src/types/conflict.ts` — added `ConflictResolutionGroup`/`ConflictResolutionListResponse`.
  Reuses the existing `ConflictClaimDetail` type as-is (identical per-claim fields on this
  endpoint). Kept separate from `ConflictGroup` since the two response shapes genuinely differ
  (no `subject_aliases` here; `superseded_claim_ids` and no `needs_review`/`resolved` counters
  are unique to this one).
- `src/lib/conflictTypes.ts` — added `temporal_succession` (teal) to the classification maps and
  `auto_resolved` (green, same treatment as the existing `resolved`) to the resolution maps.
- `src/lib/conflictFilter.ts` — added `filterConflictResolutions` (subject_name-only substring
  search; this endpoint has no aliases and no status to filter by, since every group here is
  already `auto_resolved`).
- `src/lib/api.ts` — added `fetchConflictResolutions()`.
- `src/pages/ConflictsPage.tsx` — restructured around shadcn `Tabs` (same primitive
  `EntityDetailPage.tsx` already uses), two tabs: "Needs Review ({count})" and "Auto-Resolved
  ({count})". Both endpoints are fetched **on mount regardless of which tab is active**, since
  both tab labels need real counts immediately, not just whichever tab happens to be open first.
  All of the existing Needs Review state (filters, dialogs, banner, `submitResolve`) moved into
  the `needs_review` `TabsContent` unchanged; the new `auto_resolved` `TabsContent` is
  self-contained (its own debounced search state, skeleton, error+retry, empty state, footer
  count) since it needs no dialogs or resolution logic at all.

**Verification:** same ephemeral vitest+jsdom pattern as every change this session (`--no-save`,
fully removed after; `package.json`/`package-lock.json` confirmed byte-identical). Two test
files, **11/11 passed**, run against the real components with `fetch` routed by URL to the two
real live fixtures (`/api/conflict-groups` and `/api/conflict-resolutions`, both curled during
the session):
- Both tab labels show the real `total` from their own endpoint's response on load.
- Needs Review tab is active by default and its existing cards/dialogs still render.
- Switching tabs shows the Sally Beck auto-resolved card with the correct badges and **no**
  Keep Best / All Historical / Dismiss buttons.
- The timeline renders in the real chronological order (Richard Causey → Brent Price → Louise
  Kitchen), the current claim's link has no strikethrough and the two superseded claims' links
  do, and the pills read "Current" (×1) / "Superseded" (×2).
- Searching the Auto-Resolved tab's box narrows to the matching subject.
- Switching tabs and back preserves the Needs Review tab's own search text — the two tabs' state
  don't leak into each other.
- **Regression check**, specifically because `ConflictCard.tsx` was edited to import from the
  new `shared.tsx`: Keep Best still pre-selects Sally Beck's claim (highest mention_count) and
  posts the correct `winning_claim_id`; shared-date amber highlighting and the Evidence column's
  "+6 more evidence sources" text still render exactly as before the extraction.

`tsc -b` clean. `npm run build` clean (973 kB / 296 kB gzipped — the same pre-existing >500KB
note as every day since Day 38, not addressed here for the same reason). `oxlint` clean apart
from the same already-accepted categories, plus one new instance of the already-accepted
`react(only-export-components)` pattern on `shared.tsx` (exporting `formatConflictDate` alongside
the `Pill` component — same tradeoff as `graphForces.ts`/`sortedBuckets`/`mergeFilter.ts`).

**Not done:** no undo/action for auto-resolved conflicts exists or was asked for — this tab is
read-only by design, matching the brief exactly. No real browser check — standing gap since
Day 36.

### Suggested commit message (follow-up)

```
Day 44 follow-up: add a read-only "Auto-Resolved" tab to the conflict
review queue for GET /api/conflict-resolutions (13 temporal-succession
conflicts the system ordered chronologically on its own)

Restructure ConflictsPage around shadcn Tabs: "Needs Review (N)" is
the existing human review queue unchanged; "Auto-Resolved (M)" is a
new self-contained, dialog-free tab with its own debounced search.
Both endpoints fetch on mount so both tab counts are correct
immediately regardless of which tab is open.

New AutoResolvedCard renders each conflict's claims as a vertical
timeline (same border-l/dot visual language as the entity profile's
TimelineTab), oldest first, with superseded claims dimmed and
struck through and the current claim checkmarked -- no action
buttons, since there is nothing to resolve here.

Extract Pill and formatConflictDate out of ConflictCard.tsx into a
new shared.tsx so the new card doesn't duplicate the date parser's
timezone-safety logic; verified with a regression test that
ConflictCard's own behavior is unchanged.
```

### Post-session addition: mirror alias search onto the Auto-Resolved tab

Same-day follow-up: `GET /api/conflict-resolutions` gained `subject_aliases` per conflict —
identical field to the one `/api/conflict-groups` already had (Day 44's first alias-search
follow-up). Confirmed live before touching code (`Sally Beck` → `['Sally Beck', 'Sally', 'Sally
W. Beck']`, etc.) rather than trusting the request's description of the shape.

**Changes, mirroring the existing Needs Review fix exactly:**
- `src/types/conflict.ts` — added `subject_aliases: string[]` to `ConflictResolutionGroup`
  (was previously documented in this file's own header comment as *not* present on this
  endpoint — that comment is now corrected).
- `src/lib/conflictFilter.ts` — `filterConflictResolutions` now checks the search query against
  `subject_name` OR any `subject_aliases` entry, same logic as `filterConflicts`.

No component changes needed — `AutoResolvedCard.tsx` and the Auto-Resolved tab's search input in
`ConflictsPage.tsx` were already wired to call `filterConflictResolutions`, so the new matching
behavior takes effect automatically.

**Verification:** same ephemeral vitest+jsdom pattern as every change this session (`--no-save`,
fully removed after; `package.json`/`package-lock.json` confirmed byte-identical). 5/5 checks
passed against the live `/api/conflict-resolutions` response: `filterConflictResolutions` matches
"Sheri Thomas" to the "Sheri L Thomas" group (an alias that drops the middle initial) and "Klay"
to "Kenneth Lay" (one of that group's more distinctive aliases, out of eleven); direct
subject-name search and a no-match query still behave correctly; and, driven through the actual
rendered page rather than just the pure function, typing "Klay" into the Auto-Resolved tab's live
search box narrows the card list to exactly the Kenneth Lay card. `tsc -b`, `oxlint` (same
categories as before, no new ones), and `npm run build` all clean.

### Suggested commit message (follow-up)

```
Day 44 follow-up: mirror subject_aliases search onto the Auto-Resolved
tab, matching the fix already applied to Needs Review

/api/conflict-resolutions gained subject_aliases per conflict, same
field ConflictGroup already had. filterConflictResolutions now
matches the search query against subject_aliases as well as
subject_name -- identical logic to filterConflicts, no component
changes needed since both were already wired through this function.
```

---

## Day 45 — Global Search and Filters

### What was built

A unified `/search` page: one search bar across all six node types (Person, Organization,
Claim, Evidence, Deal, Decision), grouped results, and a filter panel. `GET /api/search` was
already built by hand before this session (uncommitted `backend/src/api/app.py`/`models.py`
diffs and a new untracked `backend/src/api/routes/search.py` — not made by this session, same
recurring pattern as Days 41/44's uncommitted backend work; not touched, per CLAUDE.md §5).
Verified the real contract two ways before writing any frontend code: read
`routes/search.py`'s Cypher directly, and ran `curl 'http://localhost:8000/api/search?q=Sally+Beck'`
against the live server (read-only, no LLM quota — CLAUDE.md §9 doesn't apply to this
endpoint, so this session built directly against the live backend from the start rather than
mocking, the same as every read-only endpoint since Day 41).

**New files:**
- `src/types/search.ts` — `SearchResultItem`/`SearchResultGroup`/`GlobalSearchResponse`,
  matching `backend/src/api/models.py` field-for-field. One correction to the day brief's
  example: `mention_count` is not optional (backend model defaults it to `0`, always
  present); `confidence`/`date` are the only nullable fields.
- `src/lib/searchTypes.ts` — badge colors/labels for all 6 search result types. Reuses
  `entityTypes.ts`'s existing Person/Organization/Deal/Decision colors verbatim (so a type
  reads identically in search, the graph, and entity pages) and adds indigo (Claim) / gray
  (Evidence), the two this page needed that no earlier day did. Also holds
  `extractClaimType()` — see gap note below — and the green/amber/red confidence-threshold
  helpers the brief asked for (`>=0.9` / `>=0.7` / below).
- `src/lib/highlightMatch.tsx` — wraps the first case-insensitive match of the query in a
  `<mark>`. Deliberately simple (first match only, no regex escaping needed since it's a
  plain substring search) — the brief flagged this as a nice-to-have, skip-if-complex
  feature, and this scope was simple enough to include.
- `src/components/search/SearchBar.tsx`, `SearchFilterBar.tsx`, `SearchResultCard.tsx`,
  `SearchResultGroupSection.tsx` — the page's own component tree. `SearchResultCard`
  branches internally on `item.type` into 4 render variants (Person/Organization share one,
  Claim, Evidence, Deal/Decision share one) rather than 4 separate files, since all 4 are
  only ever used from this one page — matching this app's existing judgment call on when a
  component earns its own file (e.g. `ConflictFilterBar`'s local `SegmentedControl`) instead
  of splitting for its own sake.
- `src/pages/SearchPage.tsx` — orchestrator: query + 5 filter fields as state, 250ms
  debounce (the brief's own number, not Day 39/43's shared 300ms — page-specific, not
  extracted to a constant), fetch effect keyed on all 6 dependencies, empty/loading/error/
  no-results/results states.
- Added the `card` shadcn primitive (`npx shadcn add card`) — first use in this app.
  **Found and fixed a CLI bug before using it**: the generated `card.tsx` imported `cn` from
  a brand-new npm package literally named `cn` instead of this project's own
  `@/lib/utils` (every other shadcn component in the app — `button.tsx`, `badge.tsx`, etc. —
  imports `cn` from `@/lib/utils`). Fixed the import and ran `npm uninstall cn`;
  `package.json`/`package-lock.json` are back to exactly their pre-session state (confirmed
  by md5sum) — Day 45 added no new runtime dependency.

**Sidebar/routing:** `/search` added to `App.tsx`; "Search" added to `Sidebar.tsx` **at the
top**, above Chat, per the brief (most general entry point).

### Gaps found against the day brief (flagged, not silently worked around)

1. **`SearchResultItem` has no `claim_type`, `subject_id`, or `object_id`.** A claim result's
   `name`/`snippet` is a pre-rendered description string ("Sally Beck reports_to Richard
   Causey"), not structured fields. Two consequences, both documented in `types/search.ts`'s
   header comment:
   - **Claim cards are not clickable to an entity page.** The brief suggests "extract from
     the description or use the claim_id" — but there's no id that resolves to a working
     `/entities/{id}` link without an extra per-card resolving request nothing in the brief
     asked for, and no `/claims/:id` page exists to link to instead. This session's own
     verification checklist (item 8) only requires click-through for person/organization and
     evidence, not claims — so this was treated as the brief's own tacit acknowledgment of
     the gap, not something to route around with a fragile guess.
   - **The claim type badge is recovered best-effort**, not read from a field:
     `extractClaimType()` in `searchTypes.ts` checks the description for one of the 5 closed
     claim-type tokens as a substring (verified live: every claim description observed
     follows the literal `"{subject} {claim_type} {object}"` template). Returns `null` (no
     badge shown) rather than guessing wrong if none match.
2. **The brief's Deal/Decision link target, `/graph?node={id}`, does not match the real
   Graph Explorer.** Checked `GraphExplorerPage.tsx` before wiring this link: it reads
   `?entity=`, not `?node=` (set by Day 41's "View in Graph Explorer" button on the entity
   detail page). Used the real param — the brief's example would have silently done nothing.

### Verification

No real browser available (standing constraint since Day 36 — Playwright needs
`libnspr4`/`libnss3`, no `sudo`). Three layers, consistent with every prior day:

1. **Live integration, 15/15 checks passed** — ran `globalSearch()` from `src/lib/api.ts`
   directly against the running backend (ephemeral `tsx`, removed after; `package.json`/
   `package-lock.json` md5-confirmed unchanged). Covered: query echo; fixed group ordering;
   `total_results` equals the sum of group counts; `type=` narrows to one group;
   `claim_type=` narrows claim results; `min_confidence=` filters correctly; a broad term
   ("California") returns real cross-type results; a nonsense query returns zero groups; and
   `limit=` caps every group.
2. **DOM tests on the real page, 8/8 passed** (ephemeral vitest + jsdom + testing-library +
   jest-dom, `fetch` stubbed, `package.json`/`package-lock.json` md5-confirmed unchanged
   afterward) — empty state before any search; typing 10 characters produces exactly 1
   network request (debounce); grouped results render with correct headings; a person result
   links to `/entities/{id}` with `target="_blank"`; a claim result renders as plain text,
   never inside an `<a>`; an evidence result links to `/evidence/{id}` with
   `target="_blank"`; clicking a type filter button sends `?type=` and hides the now-irrelevant
   claim-type/date/confidence controls; the empty-results state names the active filters; a
   network failure shows "Backend unavailable" and Retry recovers into real results; the
   claim-type dropdown narrows the request; and a Deal result links to
   `/graph?entity={id}` with no `target` (same-tab, per the brief).
3. `tsc -b`, `npm run build` (984 kB / 298 kB gzipped — the bundle-size warning is
   pre-existing from Day 38's `force-graph`, not new today), and `oxlint` all clean — the one
   new warning (`SearchPage.tsx`'s reset-then-fetch effect) is the same already-accepted
   `react(set-state-in-effect)` category every other data-fetching page in this app has.

**Not done:** an actual pixel/visual check in a real browser — the standing gap since Day 36.

### Not done / deferred

- Highlighting is single-match only (first occurrence) — acceptable per the brief's own
  "skip if complex" framing; a full multi-match highlighter was not built.
- No pagination within a result group — the brief explicitly said not to (10 per type is
  the ceiling; click through to the dedicated page for more).
- The existing page-specific search boxes (Entities, Merges, Conflicts) are untouched, as
  instructed — this is an additional global search, not a replacement.

### Suggested commit message

```
Day 45: global search page across all 6 node types with grouped
results and a filter panel

New src/pages/SearchPage.tsx wired to the already-built GET
/api/search: type/claim_type/date-range/min-confidence filters,
250ms-debounced search bar, and result cards specialised per type
(Person/Organization link to the entity page, Evidence to the
evidence page, Deal/Decision into the Graph Explorer via ?entity=,
Claim rendered informational-only since the endpoint carries no
subject/object id to link from). Added the shadcn `card` primitive,
fixing a CLI-generated import bug (cn from a stray new npm package
instead of this project's @/lib/utils) before using it.

Search added to the sidebar above Chat, per the brief.
```

### Follow-up (same day): backend fixed both flagged gaps

After the initial build, two backend fixes landed on `/api/search`
(`backend/src/api/routes/search.py` + `models.py` — hand-built by the user, not
by this session):

1. **Evidence date filtering was broken.** `date_from`/`date_to` were being applied to
   Claim results only; Evidence silently ignored them. Fixed on the backend
   (`ev_filters` now includes `email_date >= $date_from` / `<= $date_to`). No frontend
   change needed — re-verified live: a broad "meeting" query with no date filter returned
   evidence spanning Aug 2000–Apr 2001, while adding `date_from=2001-01-01&date_to=2001-01-31`
   correctly narrowed every result's date into that window.
2. **`SearchResultItem` now carries `subject_id`** for claim results (still no `object_id` —
   object-side linking remains out of scope). Updated `frontend/src/types/search.ts` to add
   the field, and `ClaimCard` in `SearchResultCard.tsx` now wraps its content in the same
   `CardShell` link pattern Person/Organization/Evidence already use — `/entities/{subject_id}`
   in a new tab — falling back to plain (non-clickable) text if `subject_id` is ever null
   (defensive; not expected to trigger in practice). Verified live: `q=Sally+Beck&type=claim`
   returns `subject_id: "person:beck-sally:sally-beck-at-enron-com"`, the real entity ID.

`tsc -b` / `npm run build` clean after both changes; no dependency drift. No real browser
available to click-test in-page (standing gap since Day 36) — verified by reusing the
already-tested `CardShell` link code path plus live API confirmation of the field values.

