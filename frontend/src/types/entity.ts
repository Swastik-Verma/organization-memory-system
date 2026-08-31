// Mirrors backend/src/api/models.py's Entity section field-for-field, same approach as
// chat.ts (Day 37) and graph.ts (Day 38) — kept identical to the real Pydantic models so
// Day 41's integration is a fetch-layer swap, not a type rewrite. Verified against
// backend/src/api/models.py and backend/src/api/routes/entities.py directly.
//
// Mock-only additions, each flagged individually below (same pattern as chat.ts's
// message_date/message_subject and graph.ts's claim_count):
//
//   - EntityListItem.claim_count — the real EntityListItem model has no such field
//     (only id, name, type, mention_count). The Day 39 brief asks the list cards to show
//     a claim count regardless.
//   - EntityDetailResponse.first_seen / last_seen / claim_count — none of these three are
//     on the real EntityDetailResponse (only id, name, type, mention_count, aliases,
//     emails, org_type). The brief's detail header wants all three anyway.
//   - ClaimResult.evidence_ids — the real ClaimResult has a generic `evidence: list[dict]`
//     field instead. `source_count` (the brief's other requested field) is NOT stored
//     separately here — it's derived as `evidence_ids.length` wherever it's shown, so
//     there's exactly one number to keep in sync rather than two that could drift.
//
// Known gap for Day 41: either ask about adding claim_count/first_seen/last_seen to the
// backend models, or drop them / compute them client-side (e.g. claim_count from a
// GET .../claims call, first_seen/last_seen from scanning claim dates) when wiring the
// real endpoints.
//
// Also note: /api/entities (backend/src/api/routes/entities.py) only ever matches
// `(n:Person) OR (n:Organization)` — Deal and Decision nodes are not reachable through
// this endpoint at all today. The Day 39 brief's type filter asks for all 4 types, so
// the mocks below support all 4, but this is a real backend gap to flag before Day 41,
// not something fixable from the frontend. See the Day 39 log entry.

export interface EntityListItem {
  id: string
  name: string
  type: string // 'person' | 'organization' | 'deal' | 'decision' — lowercase
  mention_count: number
  claim_count: number // mock-only — see note above
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
  first_seen: string | null // mock-only — see note above
  last_seen: string | null // mock-only — see note above
  claim_count: number // mock-only — see note above
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
  status: string
  mention_count: number
  evidence_ids: string[] // mock-only — see note above
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
