// Mirrors backend/src/api/models.py's EvidenceDetailResponse field-for-field. Verified live
// against the running backend on Day 41.
//
// The real field is named `quote`, NOT `evidence_quote` as the Day 40 brief's example JSON
// showed — kept as `quote` to match the backend model.
//
// ── Day 41: mock-only fields removed ──────────────────────────────────────────────────
// Day 40 carried six fields the real model doesn't have. Now that the page runs on live
// data they are gone, and the components that used them were adjusted rather than fed
// fabricated values:
//
//   - subject_id / object_id — REMOVED. The real response carries only subject_name /
//     object_name, with no ids, and there is no endpoint that resolves a claim id to its
//     subject/object entity ids. ClaimSection.tsx therefore renders the subject and object
//     as plain text instead of links to /entities/:id. (Backend gap: adding subject_id /
//     object_id to EvidenceDetailResponse would restore the links — CLAUDE.md §5, not
//     changed here.)
//   - status / valid_from / valid_to — REMOVED. These live on the Claim node, not the
//     Evidence node, and evidence.py's Cypher never selects them. The claim section no
//     longer shows a status badge or a validity range.
//   - email_to — REMOVED. The real model has only `email_from`; there is no recipient
//     list. SourceEmail.tsx no longer renders a "To" row.
//
// Real fields present on the backend model but not carried here, because no UI needs them:
// `message_id`, `char_start`, `char_end`, `evidence_verified`. Highlighting uses a simple
// email_body.includes(quote) match (Day 40 brief), so the char offsets aren't needed —
// verified against live data that the quote does appear verbatim in the body.

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
}
