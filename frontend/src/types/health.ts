// Mirrors backend/src/api/models.py's Health section field-for-field.
//
// `counts` is a plain dict on the backend (`counts: dict`), keyed by Neo4j node label plus
// two extras — verified live against GET /api/health:
//   Person, Decision, Message, Organization, Evidence, Claim, Deal, total_edges, vectors
// Typed as an index signature rather than a fixed shape because the backend builds it
// dynamically from whatever labels exist in the graph.
//
// Day 42: `report` was added to the backend response (see the diff to
// backend/src/api/models.py — `HealthResponse.report: Optional[dict]`), carrying the full
// HealthMonitor.full_health_report() output used by the dashboard's cards and charts. It can
// be `null` if that report failed to generate on the backend even though the lightweight
// connectivity check (status/services/counts, unchanged) succeeded — every reader of
// `report.*` must null-check first.

export interface ServiceStatus {
  name: string
  status: string // "ok" | "error"
  detail: string | null
}

// ---------------------------------------------------------------------------------------
// report.graph_size
// ---------------------------------------------------------------------------------------

export interface HealthGraphSize {
  nodes: Record<string, number> // Person, Decision, Message, Organization, Evidence, Claim, Deal, TOTAL
  edges: Record<string, number> // SENT_TO, AFFECTS, MADE_BY, ..., TOTAL
}

// ---------------------------------------------------------------------------------------
// report.claim_quality
// ---------------------------------------------------------------------------------------

export interface EvidenceCoverage {
  no_evidence: number
  single_evidence: number
  multi_evidence: number
  avg_evidence_per_claim: number
}

export interface EvidenceVerification {
  total: number
  verified: number
  unverified: number
  unknown: number
  verification_rate: number // already a percentage, e.g. 96.7
}

export interface ClaimQuality {
  average_confidence: number // 0-1
  min_confidence: number
  max_confidence: number
  total_claims: number
  // Keys are confidence-bucket labels ("0.90-1.00", "0.70-0.89", ...). On the current corpus
  // only 2 of the possible 5 buckets are present at all — a bucket with zero claims is simply
  // absent as a key, not present with value 0. Never assume all 5 exist.
  confidence_distribution: Record<string, number>
  claims_by_type: Record<string, number> // works_with, requests_from, informs, reports_to, negotiating_with
  evidence_coverage: EvidenceCoverage
  evidence_verification: EvidenceVerification
}

// ---------------------------------------------------------------------------------------
// report.temporal_health
// ---------------------------------------------------------------------------------------

export interface TemporalHealth {
  claims_by_status: Record<string, number> // current, review, superseded
  supersession_edges: number
  conflict_pairs: number
  claims_with_closed_windows: number
  undated_claims: number
  date_range: { earliest: string; latest: string }
}

// ---------------------------------------------------------------------------------------
// report.access_levels
// ---------------------------------------------------------------------------------------

export type AccessLevelBreakdown = Record<string, number> // PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED

export type AccessLevels = Record<string, AccessLevelBreakdown> // keyed by node label (Claim, Evidence, ...)

// ---------------------------------------------------------------------------------------
// report.entity_stats
// ---------------------------------------------------------------------------------------

export interface PersonStats {
  total: number
  avg_mentions: number
  max_mentions: number
  total_aliases: number
  total_emails: number
}

export interface OrganizationStats {
  total: number
  avg_mentions: number
}

export interface TopPerson {
  name: string
  mentions: number
}

export interface EntityStats {
  persons: PersonStats
  organizations: OrganizationStats
  org_types: Record<string, number>
  top_persons: TopPerson[]
}

// ---------------------------------------------------------------------------------------
// report.data_quality
// ---------------------------------------------------------------------------------------

export interface DataQuality {
  claims_without_subject: number
  claims_without_object: number
  claims_without_evidence: number
  evidence_without_message: number
  messages_without_sender: number
  decisions_without_maker: number
  decisions_with_unresolved_affects: number
  total_unresolved_affects_strings: number
  soft_deleted_nodes: number
  quality_score: number // 0-100
}

// ---------------------------------------------------------------------------------------

export interface HealthReport {
  timestamp: string
  graph_size: HealthGraphSize
  claim_quality: ClaimQuality
  temporal_health: TemporalHealth
  access_levels: AccessLevels
  entity_stats: EntityStats
  data_quality: DataQuality
}

export interface HealthResponse {
  status: string // "healthy" | "degraded"
  services: ServiceStatus[]
  counts: Record<string, number>
  report: HealthReport | null
}

// ---------------------------------------------------------------------------------------
// Admin — mirrors backend/src/api/models.py's Admin section. Only the two counts (`total`)
// are used by the Day 42 health dashboard today; the full item lists are here too since
// they're 1:1 with the backend response and will be what Days 43-44's conflict/review pages
// build on, rather than being redefined there.
// ---------------------------------------------------------------------------------------

export interface ConflictItem {
  claim_id: string
  claim_type: string
  subject_name: string
  object_name: string
  conflicts_with: string[]
  confidence: number
}

export interface ConflictListResponse {
  conflicts: ConflictItem[]
  total: number
}

export interface ReviewItem {
  claim_id: string
  claim_type: string
  subject_name: string
  object_name: string
  status: string
  confidence: number
  reason: string
}

export interface ReviewQueueResponse {
  items: ReviewItem[]
  total: number
}
