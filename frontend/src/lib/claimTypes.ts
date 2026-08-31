// The 5 valid claim types (closed vocabulary) — see CLAUDE.md §8.6.
export const CLAIM_TYPE_LABELS: Record<string, string> = {
  reports_to: 'Reports To',
  works_with: 'Works With',
  negotiating_with: 'Negotiating With',
  requests_from: 'Requests From',
  informs: 'Informs',
}

export const CLAIM_TYPE_COLORS: Record<string, string> = {
  reports_to: 'bg-blue-100 text-blue-700',
  works_with: 'bg-emerald-100 text-emerald-700',
  negotiating_with: 'bg-amber-100 text-amber-700',
  requests_from: 'bg-purple-100 text-purple-700',
  informs: 'bg-slate-100 text-slate-700',
}

export function claimTypeLabel(claimType: string): string {
  return CLAIM_TYPE_LABELS[claimType] ?? claimType
}

export function claimTypeColor(claimType: string): string {
  return CLAIM_TYPE_COLORS[claimType] ?? 'bg-muted text-muted-foreground'
}

// Claim status colors — used on the entity detail page's Claims tab (Day 39). Status is
// a plain string on the real ClaimResult model, not part of the closed claim-type
// vocabulary above, so it gets its own small map here rather than overloading the one
// above.
export const CLAIM_STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-100 text-green-700',
  superseded: 'bg-slate-100 text-slate-500',
  review: 'bg-amber-100 text-amber-700',
}

export function claimStatusColor(status: string): string {
  return CLAIM_STATUS_COLORS[status] ?? 'bg-muted text-muted-foreground'
}

export function claimStatusLabel(status: string): string {
  if (!status) return 'Unknown'
  return status.charAt(0).toUpperCase() + status.slice(1)
}
