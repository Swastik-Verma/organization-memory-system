// Search-filtering and sorting for the merge audit log (Day 43).
//
// Extracted out of MergesPage's useMemo so a test can measure and exercise the REAL function
// rather than a copy — the same reason Day 38's graphForces.ts and Day 42's sortedBuckets are
// exported. Pure and DOM-free, so it can run in a plain script.
//
// Measured cost over the full 3,315-row corpus: ~3ms per call. That is NOT what made the
// search box lag — see the Day 43 performance note in PROJECT_CONTEXT_Day36-onward.md. The
// expensive part was re-rendering the un-virtualised table on every keystroke. This function
// is kept efficient anyway (one Intl.Collator instead of per-comparison localeCompare, and
// timestamps parsed once per row instead of ~2n·log n times inside the comparator).

import type { MergeItem } from '@/types/merge'

export type SortKey =
  | 'source_name'
  | 'target_name'
  | 'strategy'
  | 'confidence'
  | 'phase'
  | 'status'
  | 'timestamp'

export type SortDir = 'asc' | 'desc'

// Built once. `new Intl.Collator()` with default options matches String.localeCompare()'s
// default ordering, but re-uses the collator rather than constructing one per comparison.
const collator = new Intl.Collator()

/**
 * Client-side search over source/target names, then sort. `search` is matched
 * case-insensitively as a substring of either entity name — the same fields the table shows.
 */
export function filterAndSortMerges(
  merges: MergeItem[],
  search: string,
  sortKey: SortKey,
  sortDir: SortDir,
): MergeItem[] {
  const query = search.trim().toLowerCase()
  const filtered = query
    ? merges.filter(
        (m) =>
          m.source_name.toLowerCase().includes(query) ||
          m.target_name.toLowerCase().includes(query),
      )
    : merges

  const dir = sortDir === 'asc' ? 1 : -1

  if (sortKey === 'confidence') {
    return [...filtered].sort((a, b) => dir * (a.confidence - b.confidence))
  }

  if (sortKey === 'timestamp') {
    // Decorate–sort–undecorate: Date.parse runs once per row instead of twice per comparison.
    return filtered
      .map((item) => ({ item, at: Date.parse(item.timestamp) }))
      .sort((a, b) => dir * (a.at - b.at))
      .map((d) => d.item)
  }

  return [...filtered].sort((a, b) => dir * collator.compare(a[sortKey], b[sortKey]))
}
