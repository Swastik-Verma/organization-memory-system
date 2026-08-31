// Mirrors backend/src/api/models.py's Graph section field-for-field, same approach as
// src/types/chat.ts on Day 37 — kept identical to the real Pydantic models so Day 41's
// integration is a fetch-layer swap, not a type rewrite.
//
// Mock-only exception: GraphEdge.claim_count. The real GraphEdge model has no equivalent
// field (only `type`, `claim_type`, `confidence` — and the current /graph/{id}/subgraph
// route never populates `claim_type`/`confidence` either, always leaving them null). The
// day brief asks for edge thickness driven by claim count, so it's added here as a
// mock-only field, same pattern as chat.ts's message_date/message_subject. Known gap for
// Day 41: either ask about adding it to the backend, or drop the thickness-by-claim-count
// treatment when wiring the real endpoint.

export interface GraphNode {
  id: string
  label: string
  type: string // 'person' | 'organization' | 'deal' | 'decision' — lowercase, see entityTypes.ts
  mention_count: number
}

export interface GraphEdge {
  source: string
  target: string
  type: string // relationship type — mock uses the closed claim-type vocabulary directly
  claim_type: string | null
  confidence: number | null
  claim_count: number | null // mock-only — see note above
}

export interface SubgraphResponse {
  center_id: string
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphSearchResult {
  id: string
  name: string
  type: string
  mention_count: number
}

export interface GraphSearchResponse {
  query: string
  results: GraphSearchResult[]
}
