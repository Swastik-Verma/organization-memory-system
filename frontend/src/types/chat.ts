// Mirrors the Pydantic models in backend/src/api/models.py — kept field-for-field
// identical (not the day-37 task brief's simplified sketch) so Day 41's real
// integration is a fetch-layer swap, not a type rewrite.
//
// Exception: message_date and message_subject below. The real CitationItem model
// does NOT have these fields (verified against backend/src/api/models.py on Day 37) —
// only GET /api/evidence/{id} (EvidenceDetailResponse) carries email_date/email_subject.
// The Day 37 plan asks the evidence drawer to show them anyway, so they're added here
// as mock-only fields. This is a known gap for Day 41: either the backend needs a small
// addition to CitationItem, or the drawer needs to fetch /api/evidence/{evidence_id} to
// populate them for real. Flag this before starting Day 41 integration.

export interface CitationItem {
  marker: string // "[1]", "[2]", ...
  index: number // the number inside the brackets
  claim_id: string
  claim_type: string
  subject_name: string
  object_name: string
  evidence_quote: string
  evidence_id: string
  confidence: number
  message_date: string | null // mock-only — see note above
  message_subject: string | null // mock-only — see note above
}

export interface ClarificationOption {
  id: string
  name: string
  type: string
}

export interface ClarificationInfo {
  message: string
  options: ClarificationOption[]
}

export interface ChatRequest {
  question: string
  session_id: string | null
}

export interface ChatResponse {
  question: string
  effective_question: string | null
  answer: string
  citations: CitationItem[]
  clarification: ClarificationInfo | null
  session_id: string | null
  // claims, entities, retrieval_info, and context_text also exist on the real
  // ChatResponse but the chat UI doesn't need them today, so they're omitted here.
}

// ---- Conversation state (UI-only, not part of the API contract) ----

export type ConversationEntry =
  | { id: string; role: 'user'; text: string }
  | { id: string; role: 'assistant'; response: ChatResponse }
  | { id: string; role: 'error'; questionText: string; message: string }
