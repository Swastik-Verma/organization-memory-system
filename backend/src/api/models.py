"""
Pydantic models for API requests and responses.

These define the exact shape of JSON that the API accepts
and returns. FastAPI uses them for:
  1. Automatic request validation (wrong type = 422 error)
  2. Automatic response serialization (dataclass → JSON)
  3. Auto-generated Swagger/OpenAPI documentation
"""

from typing import Optional
from pydantic import BaseModel, Field


# ------------------------------------------------------------------ #
# Chat
# ------------------------------------------------------------------ #

class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""
    question: str = Field(..., min_length=1, description="Natural language question")
    session_id: Optional[str] = Field(default=None, description="Conversation session ID for multi-turn")


class EvidenceItem(BaseModel):
    """A single piece of evidence supporting a claim."""
    evidence_id: Optional[str] = None
    quote: Optional[str] = None
    message_id: Optional[str] = None
    score: Optional[float] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    email_subject: Optional[str] = None
    from_addr: Optional[str] = None
    email_date: Optional[str] = None


class ClaimResult(BaseModel):
    """A single claim in the chat response."""
    claim_id: str = ""
    claim_type: str = ""
    subject_id: str = ""
    subject_name: str = ""
    object_id: str = ""
    object_name: str = ""
    confidence: float = 0.0
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    status: str = ""
    mention_count: int = 0
    subject_mention_count: int = 0   # ADD THIS
    object_mention_count: int = 0    # ADD THIS
    relevance_score: float = 0.0
    composite_score: float = 0.0
    source: str = ""
    evidence: list[dict] = Field(default_factory=list)


class ClarificationOption(BaseModel):
    """An option shown to the user when clarification is needed."""
    id: str
    name: str
    type: str = "unknown"


class ClarificationInfo(BaseModel):
    """Clarification details when the query is ambiguous."""
    message: str
    options: list[ClarificationOption] = Field(default_factory=list)

class CitationItem(BaseModel):
    """A resolved citation from the chatbot's answer."""
    marker: str = ""           # "[1]", "[2]", etc.
    index: int = 0             # the number inside brackets
    claim_id: str = ""         # which claim this cites
    claim_type: str = ""       # reports_to, works_with, etc.
    subject_name: str = ""
    object_name: str = ""
    evidence_quote: str = ""   # the verbatim evidence text
    evidence_id: str = ""      # evidence node ID (for frontend click-through)
    confidence: float = 0.0
 

class EntityProfile(BaseModel):
    """Entity info included in chat response."""
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    mention_count: Optional[int] = None
    aliases: Optional[list[str]] = None
    emails: Optional[list[str]] = None


class RetrievalInfo(BaseModel):
    """Metadata about the retrieval process."""
    graph_results: int = 0
    semantic_results: int = 0
    merged_count: int = 0
    total_results: int = 0
    strategy: str = ""
    time_ms: float = 0.0


class ChatResponse(BaseModel):
    """Response body for POST /api/chat."""
    question: str
    effective_question: Optional[str] = None   # ADD — the rewritten question, if follow-up was detected
    answer: str = ""           # NEW — the generated natural language answer
    citations: list[CitationItem] = Field(default_factory=list)  # NEW
    claims: list[ClaimResult] = Field(default_factory=list)
    entities: list[EntityProfile] = Field(default_factory=list)
    clarification: Optional[ClarificationInfo] = None
    retrieval_info: RetrievalInfo = Field(default_factory=RetrievalInfo)
    context_text: str = ""
    session_id: Optional[str] = None           # ADD — return session_id so frontend can send it back


# ------------------------------------------------------------------ #
# Entities
# ------------------------------------------------------------------ #

class EntityListItem(BaseModel):
    """One item in the entity list."""
    id: str
    name: str
    type: str
    mention_count: int = 0


class EntityListResponse(BaseModel):
    """Response for GET /api/entities."""
    entities: list[EntityListItem] = Field(default_factory=list)
    total: int = 0
    skip: int = 0
    limit: int = 20


class EntityDetailResponse(BaseModel):
    """Response for GET /api/entities/{id}."""
    id: str
    name: str
    type: str
    mention_count: int = 0
    aliases: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    org_type: Optional[str] = None


class TimelineEvent(BaseModel):
    """One event in an entity's timeline."""
    claim_id: str
    claim_type: str
    subject_name: str = ""
    object_name: str = ""
    description: str = ""
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    status: str = ""
    confidence: float = 0.0


class EntityTimelineResponse(BaseModel):
    """Response for GET /api/entities/{id}/timeline."""
    entity_id: str
    entity_name: str = ""
    events: list[TimelineEvent] = Field(default_factory=list)


class EntityClaimsResponse(BaseModel):
    """Response for GET /api/entities/{id}/claims."""
    entity_id: str
    claims: list[ClaimResult] = Field(default_factory=list)
    total: int = 0


# ------------------------------------------------------------------ #
# Graph
# ------------------------------------------------------------------ #

class GraphNode(BaseModel):
    """A node in the subgraph response."""
    id: str
    label: str = ""
    type: str = ""
    mention_count: int = 0


class GraphEdge(BaseModel):
    """An edge in the subgraph response."""
    source: str
    target: str
    type: str = ""
    claim_type: Optional[str] = None
    confidence: Optional[float] = None


class SubgraphResponse(BaseModel):
    """Response for GET /api/graph/{id}/subgraph."""
    center_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class GraphSearchResult(BaseModel):
    """One result from graph search."""
    id: str
    name: str
    type: str
    mention_count: int = 0


class GraphSearchResponse(BaseModel):
    """Response for GET /api/graph/search."""
    query: str
    results: list[GraphSearchResult] = Field(default_factory=list)


# ------------------------------------------------------------------ #
# Evidence
# ------------------------------------------------------------------ #

class EvidenceDetailResponse(BaseModel):
    """Response for GET /api/evidence/{id}."""
    evidence_id: str
    quote: str = ""
    message_id: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    confidence: Optional[float] = None
    evidence_verified: Optional[bool] = None
    claim_id: Optional[str] = None
    claim_type: Optional[str] = None
    subject_name: Optional[str] = None
    object_name: Optional[str] = None
    email_subject: Optional[str] = None
    email_from: Optional[str] = None
    email_date: Optional[str] = None
    email_body: Optional[str] = None


# ------------------------------------------------------------------ #
# Health
# ------------------------------------------------------------------ #

class ServiceStatus(BaseModel):
    """Status of one backend service."""
    name: str
    status: str  # "ok" or "error"
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    """Response for GET /api/health."""
    status: str  # "healthy" or "degraded"
    services: list[ServiceStatus] = Field(default_factory=list)
    counts: dict = Field(default_factory=dict)
    report: Optional[dict] = None  # ADD THIS — full HealthMonitor report for the dashboard


# ------------------------------------------------------------------ #
# Admin
# ------------------------------------------------------------------ #

class ConflictItem(BaseModel):
    """One conflict in the conflict list."""
    claim_id: str
    claim_type: str = ""
    subject_name: str = ""
    object_name: str = ""
    conflicts_with: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class ConflictListResponse(BaseModel):
    """Response for GET /api/conflicts."""
    conflicts: list[ConflictItem] = Field(default_factory=list)
    total: int = 0


class ReviewItem(BaseModel):
    """One claim in the review queue."""
    claim_id: str
    claim_type: str = ""
    subject_name: str = ""
    object_name: str = ""
    status: str = ""
    confidence: float = 0.0
    reason: str = ""


class ReviewQueueResponse(BaseModel):
    """Response for GET /api/review-queue."""
    items: list[ReviewItem] = Field(default_factory=list)
    total: int = 0


# ------------------------------------------------------------------ #
# Merges
# ------------------------------------------------------------------ #

class MergeItem(BaseModel):
    """One merge in the audit log."""
    merge_id: Optional[str] = None        # null for Day 16 exact merges
    source_name: str                       # the entity that was absorbed
    target_name: str                       # the entity that survived
    source_id: Optional[str] = None        # null for Day 16
    target_id: str
    strategy: str                          # "email_match", "normalized_name_match", "fuzzy", "middle_initial", "nickname", "domain_match"
    confidence: float
    timestamp: str
    status: str = "active"                 # "active" or "undone" (Day 16 are always "active")
    phase: str                             # "exact" or "fuzzy"
    undoable: bool = False                 # True only for Day 17 fuzzy merges


class MergeListResponse(BaseModel):
    """Response for GET /api/merges."""
    merges: list[MergeItem] = Field(default_factory=list)
    total: int = 0
    exact_count: int = 0
    fuzzy_count: int = 0


class MergeUndoResponse(BaseModel):
    """Response for POST /api/merges/{merge_id}/undo."""
    success: bool
    message: str
    merge_id: str

# ------------------------------------------------------------------ #
# Conflict Review (Day 44)
# ------------------------------------------------------------------ #

class ConflictClaimDetail(BaseModel):
    """One claim within a conflict group."""
    claim_id: str
    object_id: str = ""
    object_name: str = ""
    mention_count: int = 0
    valid_from: Optional[str] = None
    confidence: float = 0.0
    evidence_id: Optional[str] = None     # ADD — first/strongest evidence, for a "View Evidence" link
    evidence_count: int = 0               # ADD — how many evidence items support this claim


class ConflictGroup(BaseModel):
    """A grouped conflict — multiple claims about the same subject."""
    conflict_id: str
    claim_type: str = ""
    subject_id: str = ""
    subject_name: str = ""
    subject_aliases: list[str] = Field(default_factory=list)  # ADD — for alias search + link
    classification: str = ""
    resolution: str = ""
    reason: str = ""
    claims: list[ConflictClaimDetail] = Field(default_factory=list)
    current_claim_id: Optional[str] = None
    timestamp: str = ""

class ConflictGroupListResponse(BaseModel):
    """Response for GET /api/conflict-groups."""
    conflicts: list[ConflictGroup] = Field(default_factory=list)
    total: int = 0
    needs_review: int = 0
    resolved: int = 0


class ConflictResolveRequest(BaseModel):
    """Request body for POST /api/conflict-groups/{conflict_id}/resolve."""
    action: str               # "keep_one", "all_historical", "dismiss"
    winning_claim_id: Optional[str] = None  # required when action is "keep_one"
    note: Optional[str] = None              # optional human note


class ConflictResolveResponse(BaseModel):
    """Response for POST /api/conflict-groups/{conflict_id}/resolve."""
    success: bool
    message: str
    conflict_id: str


class AutoResolvedConflict(BaseModel):
    """An auto-resolved temporal succession conflict (read-only)."""
    conflict_id: str
    claim_type: str = ""
    subject_id: str = ""
    subject_name: str = ""
    subject_aliases: list[str] = Field(default_factory=list)  # ADD THIS
    classification: str = ""          # always "temporal_succession"
    resolution: str = ""              # always "auto_resolved"
    reason: str = ""
    claims: list[ConflictClaimDetail] = Field(default_factory=list)
    superseded_claim_ids: list[str] = Field(default_factory=list)
    current_claim_id: Optional[str] = None
    timestamp: str = ""


class AutoResolvedListResponse(BaseModel):
    """Response for GET /api/conflict-resolutions."""
    conflicts: list[AutoResolvedConflict] = Field(default_factory=list)
    total: int = 0


# ------------------------------------------------------------------ #
# Global Search (Day 45)
# ------------------------------------------------------------------ #

class SearchResultItem(BaseModel):
    """One result from global search."""
    id: str
    name: str                              # display name / title
    type: str                              # person, organization, deal, decision, claim, evidence
    snippet: str = ""                      # matched text (truncated for long fields)
    mention_count: int = 0                 # 0 for types without mention_count
    confidence: Optional[float] = None     # claims and evidence only
    date: Optional[str] = None             # valid_from for claims, email_date for evidence
    subject_id: Optional[str] = None   # ADD THIS — claims only, links to subject's entity page

class SearchResultGroup(BaseModel):
    """Results for one node type."""
    type: str                              # person, organization, etc.
    label: str                             # "Persons", "Organizations", etc.
    results: list[SearchResultItem] = Field(default_factory=list)
    count: int = 0


class GlobalSearchResponse(BaseModel):
    """Response for GET /api/search."""
    query: str
    groups: list[SearchResultGroup] = Field(default_factory=list)
    total_results: int = 0