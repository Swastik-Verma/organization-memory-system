// Mirrors backend/src/api/models.py's Merge section field-for-field (Day 43). The
// GET /api/merges route and MergeItem/MergeListResponse/MergeUndoResponse models were
// already built by hand before this session — confirmed live via curl, not modified here.

export interface MergeItem {
  /** null for Day 16 exact merges — only Day 17 fuzzy merges have a stable operation id. */
  merge_id: string | null
  /** The entity that was absorbed. */
  source_name: string
  /** The entity that survived and still exists in the graph. */
  target_name: string
  /** null for Day 16 exact merges. */
  source_id: string | null
  target_id: string
  /** Real observed values: "email_match" / "normalized_name_match" (exact phase),
   *  "fuzzy" / "same_domain" / "nickname" (fuzzy phase). Not a closed enum here —
   *  see the Day 43 log for why the brief's "middle_initial"/"domain_match" spelling
   *  doesn't match what the backend actually returns. */
  strategy: string
  confidence: number
  timestamp: string
  status: 'active' | 'undone'
  phase: 'exact' | 'fuzzy'
  /** True only for an active Day 17 fuzzy merge — exact merges have no snapshot to restore. */
  undoable: boolean
}

export interface MergeListResponse {
  merges: MergeItem[]
  total: number
  exact_count: number
  fuzzy_count: number
}

export interface MergeUndoResponse {
  success: boolean
  message: string
  merge_id: string
}

// GET /api/merges/{merge_id} (Day 46) — full detail with both pre-merge entity snapshots.
// Only reachable for fuzzy merges (they have merge_ids and snapshots); a Day 16 exact
// merge id 404s here, matching the backend route's own restriction.

export interface MergeSnapshot {
  canonical_id: string
  canonical_name: string
  entity_type: string
  aliases: string[]
  emails: string[]
  mention_count: number
  org_type: string | null
}

export interface MergeDetailResponse {
  merge_id: string
  source_name: string
  target_name: string
  source_id: string
  target_id: string
  strategy: string
  confidence: number
  timestamp: string
  status: 'active' | 'undone'
  source_snapshot: MergeSnapshot
  target_snapshot: MergeSnapshot
}
