// Pure filtering/derivation logic for the Conflict Review Queue (Day 44), extracted out of
// ConflictsPage/ConflictCard so it can be exercised directly in a test rather than through the
// rendered DOM — same reason Day 38's graphForces.ts, Day 42's sortedBuckets and Day 43's
// mergeFilter.ts are exported functions rather than inline logic.

import type { ConflictClaimDetail, ConflictGroup, ConflictResolutionGroup } from '@/types/conflict'

export type ConflictStatusFilter = 'all' | 'needs_review' | 'resolved' | 'dismissed'

/** Client-side status filter (exact match on `resolution`) + case-insensitive substring search
 *  against `subject_name` OR any of `subject_aliases` — an alias search (e.g. "Jim Steffes")
 *  should find the conflict even though the group's canonical subject_name is "James Steffes". */
export function filterConflicts(
  conflicts: ConflictGroup[],
  status: ConflictStatusFilter,
  search: string,
): ConflictGroup[] {
  const query = search.trim().toLowerCase()
  return conflicts.filter((c) => {
    if (status !== 'all' && c.resolution !== status) return false
    if (!query) return true
    if (c.subject_name.toLowerCase().includes(query)) return true
    return c.subject_aliases.some((alias) => alias.toLowerCase().includes(query))
  })
}

/** The set of `valid_from` date strings shared by 2+ claims in one conflict group — these are
 *  the ones the card highlights, since "same person, same relationship type, same date,
 *  different objects" is the core visual signal of a contradiction. A null valid_from never
 *  counts as shared with anything. */
export function sharedDates(claims: ConflictClaimDetail[]): Set<string> {
  const counts = new Map<string, number>()
  for (const c of claims) {
    if (!c.valid_from) continue
    counts.set(c.valid_from, (counts.get(c.valid_from) ?? 0) + 1)
  }
  return new Set([...counts.entries()].filter(([, n]) => n > 1).map(([date]) => date))
}

/** Default selection for the "Keep Best" dialog: the claim with the most supporting mentions.
 *  The human still decides — this only pre-selects a sensible starting point. */
export function bestClaim(claims: ConflictClaimDetail[]): ConflictClaimDetail | null {
  if (claims.length === 0) return null
  return [...claims].sort((a, b) => b.mention_count - a.mention_count)[0]
}

/** Search-only filter for the read-only Auto-Resolved tab — no status filter exists there
 *  (every group from GET /api/conflict-resolutions is already "auto_resolved"). Matches
 *  `subject_name` OR any of `subject_aliases`, same alias-search behavior as filterConflicts
 *  above (this endpoint gained subject_aliases after the initial build, mirroring that field). */
export function filterConflictResolutions(
  conflicts: ConflictResolutionGroup[],
  search: string,
): ConflictResolutionGroup[] {
  const query = search.trim().toLowerCase()
  if (!query) return conflicts
  return conflicts.filter((c) => {
    if (c.subject_name.toLowerCase().includes(query)) return true
    return c.subject_aliases.some((alias) => alias.toLowerCase().includes(query))
  })
}
