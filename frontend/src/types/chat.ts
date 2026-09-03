// Mirrors the Pydantic models in backend/src/api/models.py — kept field-for-field
// identical (not the day-37 task brief's simplified sketch) so Day 41's real
// integration is a fetch-layer swap, not a type rewrite.
//
// Day 41 update: message_date / message_subject have been REMOVED from CitationItem. They
// were mock-only fields added on Day 37 for the evidence drawer's "Source" section; the
// real CitationItem returned by POST /api/chat has never had them. The drawer now fetches
// GET /api/evidence/{evidence_id} when it opens and reads email_date / email_subject from
// EvidenceDetailResponse instead — see EvidenceDrawer.tsx.

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
