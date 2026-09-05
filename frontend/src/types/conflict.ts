// Conflict Review Queue types (Day 44) — mirrors backend/src/api/models.py's Day 44 section
// field-for-field, confirmed live against a running GET /api/conflict-groups before writing
// these. Distinct from src/types/health.ts's ConflictItem/ConflictListResponse (Day 42, the
// older flat /api/conflicts endpoint) — that endpoint returns individual claim pairs, this one
// returns claims already grouped by subject + claim_type, which is what this page renders.

export interface ConflictClaimDetail {
  claim_id: string
  object_id: string
  object_name: string
  mention_count: number
  valid_from: string | null
  confidence: number
  /** Added after the initial Day 44 build. Null is possible in principle (backend model
   *  declares it Optional) though every live claim has one today — always null-check before
   *  linking. */
  evidence_id: string | null
  /** Total evidence sources backing this one claim; evidence_id links to just one of them. */
  evidence_count: number
}

export interface ConflictGroup {
  conflict_id: string
  claim_type: string
  subject_id: string
  subject_name: string
  /** Alternate names for the subject (aliases from entity resolution). Added after the
   *  initial Day 44 build, alongside the per-claim evidence fields above. */
  subject_aliases: string[]
  /** "direct_contradiction" today on every live conflict; "undated" is a real backend value
   *  the model supports but the current corpus never produces it. */
  classification: string
  /** "needs_review" | "resolved" | "dismissed" */
  resolution: string
  reason: string
  claims: ConflictClaimDetail[]
  current_claim_id: string | null
  timestamp: string
}

export interface ConflictGroupListResponse {
  conflicts: ConflictGroup[]
  total: number
  needs_review: number
  resolved: number
}

export type ConflictResolveAction = 'keep_one' | 'all_historical' | 'dismiss'

export interface ConflictResolveRequest {
  action: ConflictResolveAction
  winning_claim_id?: string
  note?: string
}

export interface ConflictResolveResponse {
  success: boolean
  message: string
  conflict_id: string
}

// ---------------------------------------------------------------------------------------
// Auto-Resolved (temporal succession) — GET /api/conflict-resolutions. Read-only audit trail
// of conflicts the system resolved itself by ordering claims chronologically, distinct from
// ConflictGroup above (which is the human review queue, /api/conflict-groups). Confirmed live
// before writing these: claims already arrive sorted ascending by valid_from, current_claim_id
// is always the last claim in that sorted array, and superseded_claim_ids is always exactly
// "every other claim's id" — verified across all 13 live groups, but current_claim_id is still
// matched by id per claim rather than assumed by array position, since the response shape
// doesn't guarantee that ordering will hold forever. subject_aliases was added to this endpoint
// after the initial build, mirroring the same field ConflictGroup already had.
// ---------------------------------------------------------------------------------------

export interface ConflictResolutionGroup {
  conflict_id: string
  claim_type: string
  subject_id: string
  subject_name: string
  /** Alternate names for the subject — same field/purpose as ConflictGroup.subject_aliases. */
  subject_aliases: string[]
  /** "temporal_succession" on every live conflict from this endpoint. */
  classification: string
  /** "auto_resolved" on every live conflict from this endpoint. */
  resolution: string
  reason: string
  /** Already sorted chronologically ascending (oldest valid_from first) by the backend. */
  claims: ConflictClaimDetail[]
  superseded_claim_ids: string[]
  current_claim_id: string | null
  timestamp: string
}

export interface ConflictResolutionListResponse {
  conflicts: ConflictResolutionGroup[]
  total: number
}
