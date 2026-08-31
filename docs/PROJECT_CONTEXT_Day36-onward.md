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
