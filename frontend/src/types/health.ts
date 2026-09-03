// Mirrors backend/src/api/models.py's Health section field-for-field.
//
// `counts` is a plain dict on the backend (`counts: dict`), keyed by Neo4j node label plus
// two extras — verified live against GET /api/health:
//   Person, Decision, Message, Organization, Evidence, Claim, Deal, total_edges, vectors
// Typed as an index signature rather than a fixed shape because the backend builds it
// dynamically from whatever labels exist in the graph.

export interface ServiceStatus {
  name: string
  status: string // "ok" | "error"
  detail: string | null
}

export interface HealthResponse {
  status: string // "healthy" | "degraded"
  services: ServiceStatus[]
  counts: Record<string, number>
}
