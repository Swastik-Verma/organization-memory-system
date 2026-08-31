// Mirrors backend/src/api/models.py's EvidenceDetailResponse field-for-field, same approach
// as chat.ts (Day 37), graph.ts (Day 38), and entity.ts (Day 39) — verified directly against
// backend/src/api/models.py and backend/src/api/routes/evidence.py.
//
// The real field is named `quote`, NOT `evidence_quote` as the Day 40 brief's example JSON
// shows — kept as `quote` here to match the backend model, since every other type file in
// this app prioritizes matching the real Pydantic model over a task brief's illustrative
// shape (see chat.ts's header comment for the same call made on Day 37).
//
// Real fields present on the backend model but NOT carried here, since today's UI doesn't
// need them (same "field-for-field but UI-need-gated" approach chat.ts took with
// claims/entities/retrieval_info/context_text): `message_id`, `char_start`, `char_end`,
// `evidence_verified`. The brief's highlighting requirement explicitly asks for a simple
// `email_body.includes(quote)` string match rather than char-offset-based highlighting, so
// char_start/char_end aren't needed to implement it.
//
// Mock-only additions, each flagged individually (same pattern as every prior mock day):
//
//   - subject_id / object_id — the real model only returns subject_name/object_name (no
//     ids). The Day 40 brief wants the claim section's subject/object to be clickable links
//     to /entities/:id, which needs an id. Real integration will need to either add these to
//     the backend model or have the frontend resolve name -> id via a lookup.
//   - status, valid_from, valid_to — these live on the Claim node in the real schema, not
//     the Evidence node (see the Cypher query in backend/src/api/routes/evidence.py, which
//     never selects them), so EvidenceDetailResponse genuinely has no such fields. The
//     brief's claim section wants a status badge and temporal validity shown anyway.
//   - email_to — the real model has only a single `email_from`, no recipient list. The
//     brief's example response includes one.
//
// Known gap for Day 41, same shape as every prior day's gap note: before wiring the real
// endpoint, either ask about adding subject_id/object_id/status/valid_from/valid_to to
// EvidenceDetailResponse (a backend change, needs sign-off per CLAUDE.md §5), or have this
// page fetch GET /api/claims/{claim_id} (if such a route exists) / cross-reference the
// entity list to resolve ids, and drop status/valid_from/valid_to/email_to entirely if no
// equivalent backend source is added. Flag this at the start of Day 41.

export interface EvidenceDetailResponse {
  evidence_id: string
  quote: string
  confidence: number | null
  claim_id: string | null
  claim_type: string | null
  subject_name: string | null
  object_name: string | null
  email_subject: string | null
  email_from: string | null
  email_date: string | null
  email_body: string | null

  // ---- mock-only additions — see header comment ----
  subject_id: string
  object_id: string
  status: string
  valid_from: string | null
  valid_to: string | null
  email_to: string[]
}
