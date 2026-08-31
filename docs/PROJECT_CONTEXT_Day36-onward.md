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
