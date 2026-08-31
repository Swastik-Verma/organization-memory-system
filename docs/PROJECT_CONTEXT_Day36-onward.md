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
