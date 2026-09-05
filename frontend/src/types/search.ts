// Mirrors backend/src/api/routes/search.py + models.py's Search section field-for-field.
// Verified live against the running backend (GET /api/search?q=Sally+Beck) before writing
// this file, per Day 45's brief — same "read the real route, don't trust the brief's example
// blindly" approach as Days 39/41.
//
// ── Backend follow-up (post-session fixes) ────────────────────────────────────────────────
// Two gaps flagged at the end of Day 45 were fixed on the backend directly:
//  1. Evidence results now respect date_from/date_to (previously silently ignored for
//     Evidence — only Claim honored them).
//  2. SearchResultItem now carries subject_id for claim results, so claim cards can link to
//     the subject's entity page. object_id is still not present — object-side linking remains
//     out of scope.

export type SearchResultType = 'person' | 'organization' | 'claim' | 'evidence' | 'deal' | 'decision'

export interface SearchResultItem {
  id: string
  name: string
  type: SearchResultType
  snippet: string
  /** Always present (backend model default 0) — meaningful for person/organization only,
   *  0 for claim/evidence/deal/decision. */
  mention_count: number
  /** Populated for claim/evidence only; null for person/organization/deal/decision. */
  confidence: number | null
  /** Populated for claim (valid_from) and evidence (email_date) only. */
  date: string | null
  /** Claim results only: the subject entity's id, for a "View entity" link. Null for every
   *  other type, and defensively possible-but-unexpected null on a claim. */
  subject_id: string | null
}

export interface SearchResultGroup {
  type: SearchResultType
  label: string
  results: SearchResultItem[]
  count: number
}

export interface GlobalSearchResponse {
  query: string
  groups: SearchResultGroup[]
  total_results: number
}
