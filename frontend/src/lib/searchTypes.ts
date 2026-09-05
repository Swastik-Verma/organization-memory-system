// Colors/labels for the Global Search page (Day 45). Only this page needs colors for
// Claim/Evidence as *node types* (indigo/gray) — entityTypes.ts only covers the 4 real graph
// entity types (Person/Organization/Deal/Decision), which stay exactly those colors here too
// so a type reads identically whether you're looking at the graph, an entity page, or search.

import { entityTypeBadgeClass, entityTypeColor, entityTypeLabel } from '@/lib/entityTypes'
import type { SearchResultType } from '@/types/search'

export const SEARCH_TYPE_ORDER: SearchResultType[] = [
  'person',
  'organization',
  'claim',
  'evidence',
  'deal',
  'decision',
]

// Plural, for the "All | Persons | Organizations | ..." filter buttons — matches the labels
// the backend itself uses for group headers (TYPE_LABELS in search.py), kept as a static
// list here so the buttons render before any search has run (a group only exists in the
// response once it has at least one result).
export const SEARCH_TYPE_FILTER_LABELS: Record<SearchResultType, string> = {
  person: 'Persons',
  organization: 'Organizations',
  claim: 'Claims',
  evidence: 'Evidence',
  deal: 'Deals',
  decision: 'Decisions',
}

const SEARCH_TYPE_SINGULAR_LABELS: Record<SearchResultType, string> = {
  person: 'Person',
  organization: 'Organization',
  claim: 'Claim',
  evidence: 'Evidence',
  deal: 'Deal',
  decision: 'Decision',
}

export function searchTypeLabel(type: SearchResultType): string {
  return SEARCH_TYPE_SINGULAR_LABELS[type] ?? entityTypeLabel(type)
}

const EXTRA_BADGE_CLASSES: Partial<Record<SearchResultType, string>> = {
  claim: 'bg-indigo-100 text-indigo-700',
  evidence: 'bg-gray-100 text-gray-700',
}

/** Static Tailwind classes only (JIT scanner needs literal strings) — same constraint noted
 *  in entityTypes.ts. Person/Organization/Deal/Decision reuse that file's classes verbatim. */
export function searchTypeBadgeClass(type: SearchResultType): string {
  return EXTRA_BADGE_CLASSES[type] ?? entityTypeBadgeClass(type)
}

const EXTRA_COLORS: Partial<Record<SearchResultType, string>> = {
  claim: '#4f46e5', // indigo
  evidence: '#6b7280', // gray
}

export function searchTypeColor(type: SearchResultType): string {
  return EXTRA_COLORS[type] ?? entityTypeColor(type)
}

// ── Confidence thresholds (claim/evidence cards only) ────────────────────────────────────
// green >= 0.9, amber >= 0.7, red < 0.7, per the Day 45 brief.
export function confidenceLevelClass(confidence: number): string {
  if (confidence >= 0.9) return 'text-green-700 bg-green-100'
  if (confidence >= 0.7) return 'text-amber-700 bg-amber-100'
  return 'text-red-700 bg-red-100'
}

export function confidenceBarClass(confidence: number): string {
  if (confidence >= 0.9) return 'bg-green-500'
  if (confidence >= 0.7) return 'bg-amber-500'
  return 'bg-red-500'
}

// ── Best-effort claim_type extraction ─────────────────────────────────────────────────────
// GET /api/search's SearchResultItem carries no claim_type field (see types/search.ts header
// comment) — only a pre-rendered `name`/`snippet` description. Every claim description
// observed live against the backend follows "{subject} {claim_type} {object}" verbatim, and
// the claim_type vocabulary is closed (CLAUDE.md §8.6), so it can be recovered by checking
// for one of the 5 known tokens as a substring. Returns null if none match (falls back to no
// badge rather than a wrong guess) — this is a display nicety, not something claim search
// results structurally depend on.
const CLAIM_TYPE_TOKENS = ['negotiating_with', 'requests_from', 'reports_to', 'works_with', 'informs']

export function extractClaimType(description: string): string | null {
  return CLAIM_TYPE_TOKENS.find((token) => description.includes(token)) ?? null
}
