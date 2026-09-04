// Merge audit log badge colors/labels (Day 43). Same pattern as entityTypes.ts/claimTypes.ts:
// a plain lookup map + fallback, static Tailwind classes (not template strings) so Tailwind
// v4's JIT scanner picks them up.
//
// Strategy values here are the REAL ones observed live from GET /api/merges, not the Day 43
// brief's list — the brief names "middle_initial" and "domain_match", but the backend has no
// "middle_initial" merges at all and calls the domain-based strategy "same_domain". Colors
// deliberately avoid blue/violet/emerald/amber, since those are the entity-type palette
// (CLAUDE.md §6) and reusing them here would make a merge row's strategy badge look like it's
// naming a Person/Organization/Deal/Decision type.
export const STRATEGY_LABELS: Record<string, string> = {
  email_match: 'Email Match',
  normalized_name_match: 'Normalized Name',
  fuzzy: 'Fuzzy',
  nickname: 'Nickname',
  same_domain: 'Same Domain',
  domain_match: 'Domain Match', // kept in case the backend data ever uses this spelling
  middle_initial: 'Middle Initial', // kept in case the backend data ever uses this spelling
}

export const STRATEGY_COLORS: Record<string, string> = {
  email_match: 'bg-cyan-100 text-cyan-700',
  normalized_name_match: 'bg-teal-100 text-teal-700',
  fuzzy: 'bg-fuchsia-100 text-fuchsia-700',
  nickname: 'bg-rose-100 text-rose-700',
  same_domain: 'bg-orange-100 text-orange-700',
  domain_match: 'bg-orange-100 text-orange-700',
  middle_initial: 'bg-lime-100 text-lime-700',
}

export function strategyLabel(strategy: string): string {
  return STRATEGY_LABELS[strategy] ?? strategy
}

export function strategyColor(strategy: string): string {
  return STRATEGY_COLORS[strategy] ?? 'bg-muted text-muted-foreground'
}

// Phase badge — "Exact" gray, "Fuzzy" indigo (the app's accent color, CLAUDE.md §6).
export const PHASE_LABELS: Record<string, string> = {
  exact: 'Exact',
  fuzzy: 'Fuzzy',
}

export const PHASE_COLORS: Record<string, string> = {
  exact: 'bg-slate-100 text-slate-600',
  fuzzy: 'bg-indigo-100 text-indigo-700',
}

export function phaseLabel(phase: string): string {
  return PHASE_LABELS[phase] ?? phase
}

export function phaseColor(phase: string): string {
  return PHASE_COLORS[phase] ?? 'bg-muted text-muted-foreground'
}

// Status badge — "Active" green, "Undone" amber.
export const MERGE_STATUS_LABELS: Record<string, string> = {
  active: 'Active',
  undone: 'Undone',
}

export const MERGE_STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-100 text-green-700',
  undone: 'bg-amber-100 text-amber-700',
}

export function mergeStatusLabel(status: string): string {
  return MERGE_STATUS_LABELS[status] ?? status
}

export function mergeStatusColor(status: string): string {
  return MERGE_STATUS_COLORS[status] ?? 'bg-muted text-muted-foreground'
}
