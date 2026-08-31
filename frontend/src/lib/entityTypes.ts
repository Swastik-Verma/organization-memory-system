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

// Tailwind classes for the pill badges used in the entities list/detail pages (Day 39).
// Static classes (not built from a template string) are required here — Tailwind v4's
// JIT scanner only picks up class names it can find literally in source. Colocated with
// the color/label maps above rather than in a component so any badge in the app renders
// entity types identically.
export const ENTITY_TYPE_BADGE_CLASSES: Record<string, string> = {
  person: 'bg-entity-person/10 text-entity-person',
  organization: 'bg-entity-organization/10 text-entity-organization',
  deal: 'bg-entity-deal/10 text-entity-deal',
  decision: 'bg-entity-decision/10 text-entity-decision',
}

const FALLBACK_BADGE_CLASSES = 'bg-muted text-muted-foreground'

export function entityTypeBadgeClass(type: string): string {
  return ENTITY_TYPE_BADGE_CLASSES[type.toLowerCase()] ?? FALLBACK_BADGE_CLASSES
}
