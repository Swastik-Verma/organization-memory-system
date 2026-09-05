// Conflict Review Queue badge colors/labels (Day 44). Same lookup-map-plus-fallback pattern as
// entityTypes.ts/claimTypes.ts/mergeTypes.ts.

export const CLASSIFICATION_LABELS: Record<string, string> = {
  direct_contradiction: 'Direct Contradiction',
  undated: 'Undated',
  temporal_succession: 'Temporal Succession',
}

export const CLASSIFICATION_COLORS: Record<string, string> = {
  direct_contradiction: 'bg-red-100 text-red-700',
  undated: 'bg-amber-100 text-amber-700',
  temporal_succession: 'bg-teal-100 text-teal-700',
}

export function classificationLabel(classification: string): string {
  return CLASSIFICATION_LABELS[classification] ?? classification
}

export function classificationColor(classification: string): string {
  return CLASSIFICATION_COLORS[classification] ?? 'bg-muted text-muted-foreground'
}

export const RESOLUTION_LABELS: Record<string, string> = {
  needs_review: 'Needs Review',
  resolved: 'Resolved',
  dismissed: 'Dismissed',
  auto_resolved: 'Auto-Resolved',
}

export const RESOLUTION_COLORS: Record<string, string> = {
  needs_review: 'bg-amber-100 text-amber-700',
  resolved: 'bg-green-100 text-green-700',
  dismissed: 'bg-slate-100 text-slate-600',
  auto_resolved: 'bg-green-100 text-green-700',
}

export function resolutionLabel(resolution: string): string {
  return RESOLUTION_LABELS[resolution] ?? resolution
}

export function resolutionColor(resolution: string): string {
  return RESOLUTION_COLORS[resolution] ?? 'bg-muted text-muted-foreground'
}
