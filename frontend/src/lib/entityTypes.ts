// Entity node type colors/labels — see CLAUDE.md §6 design tokens (also registered as
// Tailwind utilities in src/index.css, e.g. bg-entity-person, for non-canvas UI).
//
// Keyed lowercase: the real backend (backend/src/api/routes/graph.py) lowercases
// `labels(neighbor)[0]` before returning it (e.g. "person", not "Person"), and
// GraphSearchResult does the same. Mirrored here so Day 41 doesn't need a casing fix.
export const ENTITY_TYPE_COLORS: Record<string, string> = {
  person: '#3b82f6', // blue
  organization: '#8b5cf6', // violet
  deal: '#10b981', // emerald
  decision: '#f59e0b', // amber
}

export const ENTITY_TYPE_LABELS: Record<string, string> = {
  person: 'Person',
  organization: 'Organization',
  deal: 'Deal',
  decision: 'Decision',
}

const FALLBACK_COLOR = '#94a3b8' // slate — unknown/unmapped type (e.g. a Claim node)

export function entityTypeColor(type: string): string {
  return ENTITY_TYPE_COLORS[type.toLowerCase()] ?? FALLBACK_COLOR
}

export function entityTypeLabel(type: string): string {
  return ENTITY_TYPE_LABELS[type.toLowerCase()] ?? type
}
