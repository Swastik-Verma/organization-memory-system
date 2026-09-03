// Mirrors backend/src/api/models.py's Graph section. Verified live against the running
// backend on Day 41.
//
// ── What the raw subgraph endpoint actually returns ───────────────────────────────────
// GraphEdge.type is the raw Neo4j RELATIONSHIP type, in SCREAMING_CASE:
//   SUBJECT, OBJECT, SUPPORTED_BY, FROM_MESSAGE, SENT_BY, SENT_TO,
//   MADE_BY, AFFECTS, SUPERSEDES, CONFLICTS_WITH, PARTY
// The five claim types (works_with, reports_to, negotiating_with, requests_from, informs)
// are NOT relationship types — they are a `claim_type` property on Claim NODES. A claim is
// modelled as (:Person)<-[:SUBJECT]-(:Claim)-[:OBJECT]->(:Person), so the raw endpoint can
// never return a direct "Sally Beck --reports_to--> Richard Causey" edge at any depth.
//
// GraphEdge.claim_type and GraphEdge.confidence are declared on the backend model but the
// route never populates them — both are always null in the raw response.
//
// src/lib/graphData.ts composes a usable entity-to-entity graph out of this endpoint plus
// /api/entities/{id}/claims, and fills claim_type / confidence / claim_count itself. Read
// that file's header for the full rationale.

export interface GraphNode {
  id: string
  label: string
  type: string // 'person' | 'organization' | 'deal' | 'decision' — lowercase, see entityTypes.ts
  mention_count: number
}

export interface GraphEdge {
  source: string
  target: string
  /** Display relationship type. Raw endpoint: SCREAMING_CASE Neo4j type. After
   *  graphData.ts composition: one of the 8 lowercase types the UI renders. */
  type: string
  /** Populated by graphData.ts for claim-derived edges; always null from the raw endpoint. */
  claim_type: string | null
  /** Populated by graphData.ts (max confidence across merged claims); null from the raw endpoint. */
  confidence: number | null
  /** Number of claims collapsed into this edge. Derived by graphData.ts; not a backend field. */
  claim_count: number | null
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
