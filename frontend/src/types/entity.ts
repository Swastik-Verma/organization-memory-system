// Mirrors backend/src/api/models.py's Entity section field-for-field. Verified live against
// the running backend on Day 41 — every field below is one the API actually returns.
//
// ── Day 41: mock-only fields removed ──────────────────────────────────────────────────
// Days 39-40 carried several fields the real models don't have. Now that the pages are on
// live data, each has been resolved rather than left as a lie in the type:
//
//   - EntityListItem.claim_count — REMOVED. The real EntityListItem has no such field, and
//     there is no way to obtain it for a whole page of entities without one extra request
//     per row. EntityCard.tsx now shows mention_count only.
//   - EntityDetailResponse.claim_count / first_seen / last_seen — REMOVED from the type.
//     They are now DERIVED client-side in EntityDetailPage.tsx from a single
//     GET /api/entities/{id}/claims call (claim_count = response.total; first_seen /
//     last_seen = min/max of valid_from) and passed to EntityHeader as a separate
//     `stats` prop. Deriving claim_count from the same call the Claims tab renders is
//     deliberate: the header's "N claims" and the Claims tab's list are then guaranteed to
//     be the same number rather than two independent counts that can disagree.
//   - ClaimResult.evidence_ids — REPLACED by the real `evidence: EvidenceRef[]` field.
//
// ── KNOWN BACKEND GAP (flagged, not worked around) ────────────────────────────────────
// `ClaimResult.evidence` is declared as `list[dict]` on the backend model but
// backend/src/api/routes/entities.py's claims query NEVER selects or populates it — it is
// always []. The data exists: all 5,586 Claim nodes have a (:Claim)-[:SUPPORTED_BY]->
// (:Evidence) relationship in Neo4j, the route simply doesn't traverse it. Consequence:
// the "View evidence" link on every claim card falls back to the Day 39 "No supporting
// evidence indexed yet." empty state, for every claim. Fixing this needs a backend change
// (CLAUDE.md §5 — not made here). Chat citations are unaffected: CitationItem carries a
// real evidence_id, so the chat evidence drawer and /evidence/:id page work correctly.

export interface EntityListItem {
  id: string
  name: string
  type: string // 'person' | 'organization' — lowercase, see entityTypes.ts
  mention_count: number
}

export interface EntityListResponse {
  entities: EntityListItem[]
  total: number
  skip: number
  limit: number
}

export interface EntityDetailResponse {
  id: string
  name: string
  type: string
  mention_count: number
  aliases: string[]
  emails: string[]
  org_type: string | null
}

/** Counts/date-range derived client-side from the claims response — see header note. */
export interface EntityStats {
  claim_count: number
  first_seen: string | null
  last_seen: string | null
}

/** One entry of ClaimResult.evidence. Always absent in practice today — see header note. */
export interface EvidenceRef {
  evidence_id?: string
  quote?: string
  message_id?: string
  email_subject?: string
  email_date?: string
}

export interface ClaimResult {
  claim_id: string
  claim_type: string
  subject_id: string
  subject_name: string
  object_id: string
  object_name: string
  confidence: number
  valid_from: string | null
  valid_to: string | null
  status: string // 'current' | 'superseded' | 'review' — see claimTypes.ts
  /** Mentions of the CLAIM — how many emails asserted this one fact. Not an entity count. */
  mention_count: number
  /** The subject ENTITY's own Person/Organization.mention_count. Distinct from the
   *  claim-level mention_count above; this is the same number /api/entities/{id} reports. */
  subject_mention_count: number
  /** The object ENTITY's own Person/Organization.mention_count. */
  object_mention_count: number
  evidence: EvidenceRef[]
}

export interface EntityClaimsResponse {
  entity_id: string
  claims: ClaimResult[]
  total: number
}

export interface TimelineEvent {
  claim_id: string
  claim_type: string
  subject_name: string
  object_name: string
  description: string
  valid_from: string | null
  valid_to: string | null
  status: string
  confidence: number
}

export interface EntityTimelineResponse {
  entity_id: string
  entity_name: string
  events: TimelineEvent[]
}
