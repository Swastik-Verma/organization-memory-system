"""
Day 22 — Graph Node Schema (Revised)

Pydantic models representing the Neo4j node types. These are used by the
graph loader (Day 23) to validate data before writing to Neo4j.

Replaces the Day 5 version. Aligned with:
- entity_resolution_fuzzy.json (Person/Organization)
- resolved_claims.jsonl (Claim + Evidence)
- extractions_final.jsonl (Deal, Decision)
- extraction_subset.jsonl (Message)

Key changes from Day 5:
- Person ID includes email slug (Day 16)
- Claim ID is fact-level, not mention-level (Day 18)
- Claim has supersedes/superseded_by/conflicts_with (Day 19)
- All nodes have soft-delete fields (Day 20)
- Organization org_type is a closed enum (normalization)
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# ENUMS
# ============================================================

class OrgType(str, Enum):
    """Normalized organization types. Mapped from 120+ free-text variants."""
    COMPANY = "company"
    GOVERNMENT = "government"
    NONPROFIT = "nonprofit"
    UNIVERSITY = "university"
    INTERNAL_DIVISION = "internal_division"
    OTHER = "other"


class ClaimType(str, Enum):
    """Closed vocabulary for relationship/claim types."""
    REPORTS_TO = "reports_to"
    WORKS_WITH = "works_with"
    REQUESTS_FROM = "requests_from"
    NEGOTIATING_WITH = "negotiating_with"
    INFORMS = "informs"


class ClaimStatus(str, Enum):
    """Lifecycle status of a claim."""
    CURRENT = "current"
    SUPERSEDED = "superseded"
    REVIEW = "review"
    ARCHIVED = "archived"


# ============================================================
# SOFT DELETE MIXIN
# ============================================================

class SoftDeleteMixin(BaseModel):
    """Fields shared by all node types for soft-delete support."""
    is_deleted: bool = False
    deleted_at: Optional[str] = None      # ISO datetime string
    deletion_reason: Optional[str] = None


# ============================================================
# ENTITY NODES
# ============================================================

class GraphPerson(SoftDeleteMixin):
    """
    A canonical person entity.

    Source: entity_resolution_fuzzy.json → canonical_entities
    ID format: person:{normalized-name}:{email-slug}
    Example: person:kean-steven:steven-kean-at-enron-com
    """
    id: str                                  # Canonical ID from entity resolver
    canonical_name: str                      # Best display name
    aliases: list[str] = Field(default_factory=list)   # All name variants seen
    emails: list[str] = Field(default_factory=list)    # All email addresses
    mention_count: int = 0                   # Total mentions across all emails
    first_seen: Optional[str] = None         # Earliest email date (populated at ingestion)
    last_seen: Optional[str] = None          # Latest email date (populated at ingestion)


class GraphOrganization(SoftDeleteMixin):
    """
    A canonical organization entity.

    Source: entity_resolution_fuzzy.json → canonical_entities
    ID format: org:{normalized-name}
    Example: org:enron
    """
    id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    mention_count: int = 0
    org_type: Optional[OrgType] = None       # Normalized from 120+ free-text variants


class GraphDeal(SoftDeleteMixin):
    """
    A business deal or transaction.

    Source: extractions_final.jsonl → deals (approved only)
    ID format: deal:{slugified-name}
    """
    id: str
    name: str
    status: Optional[str] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None


class GraphDecision(SoftDeleteMixin):
    """
    A business decision.

    Source: extractions_final.jsonl → decisions (approved only)
    ID format: decision:{sha256(message_id + description)[:16]}

    Note: made_by is stored as an edge (MADE_BY → Person), not a property.
    affects_unresolved stores strings that couldn't be resolved to known entities.
    """
    id: str
    description: str
    made_by_name: Optional[str] = None       # Denormalized for display; edge is authoritative
    affects_unresolved: list[str] = Field(default_factory=list)  # Strings with no entity match
    first_seen: Optional[str] = None


# ============================================================
# CLAIM & EVIDENCE NODES
# ============================================================

class GraphEvidence(SoftDeleteMixin):
    """
    A verbatim quote from an email supporting a claim.

    Source: embedded in each claim's evidence list in resolved_claims.jsonl
    ID format: evidence:{sha256(message_id + quote)[:16]}
    """
    id: str
    quote: str
    char_start: Optional[int] = None         # Offset into source email body
    char_end: Optional[int] = None
    evidence_verified: Optional[bool] = None  # True if quote found in body
    confidence: float = 0.0
    email_date: Optional[str] = None          # Date of the source email
    in_quoted_block: Optional[bool] = None    # True if quote is in noise region


class GraphClaim(SoftDeleteMixin):
    """
    A deduplicated relationship claim between two people.

    Source: resolved_claims.jsonl
    ID format: claim:{sha256(subject_id|claim_type|object_id)[:16]}

    This is a REIFIED RELATIONSHIP — stored as a node, not an edge,
    because it needs to be the endpoint of other relationships
    (evidence, supersession, conflicts).

    One Claim per fact. Multiple emails asserting the same fact
    produce multiple Evidence nodes linked to one Claim via SUPPORTED_BY.
    """
    id: str
    claim_type: ClaimType                    # reports_to, works_with, etc.
    description: str                          # Human-readable: "X reports_to Y"
    confidence: float                         # Max across evidence items
    valid_from: Optional[str] = None          # Earliest email date asserting this
    valid_to: Optional[str] = None            # Null = still true; set by temporal resolution
    status: ClaimStatus = ClaimStatus.CURRENT
    mention_count: int = 1                    # How many emails stated this fact
    prompt_version: Optional[str] = None      # SHA-256 hash of extraction prompt
    model_name: Optional[str] = None          # LLM model used for extraction

    # Temporal succession (Day 19)
    supersedes: Optional[str] = None          # Claim ID this replaced
    superseded_by: Optional[str] = None       # Claim ID that replaced this
    conflicts_with: list[str] = Field(default_factory=list)  # Bidirectional conflict links

    # Denormalized display names (avoid graph traversal for simple display)
    subject_name: Optional[str] = None
    object_name: Optional[str] = None


# ============================================================
# MESSAGE NODE
# ============================================================

class GraphMessage(SoftDeleteMixin):
    """
    A source email from the Enron corpus.

    Source: extraction_subset.jsonl (minus duplicate_ids.json)
    ID: original RFC 2822 Message-ID (unchanged)

    The full body is stored for the frontend evidence panel —
    when a user clicks a citation, we highlight the exact quote
    within the full email text.
    """
    message_id: str                           # RFC 2822 Message-ID (the PK)
    date: Optional[str] = None
    subject: Optional[str] = None
    from_addr: Optional[str] = None
    body: Optional[str] = None                # Full email body (for evidence panel)
    x_origin: Optional[str] = None            # Mailbox owner
    x_folder: Optional[str] = None


# ============================================================
# ORG_TYPE NORMALIZATION MAP
# ============================================================

# Maps the 120+ free-text org_type values from extraction to 6 categories.
# Applied during graph loading (Day 23), not here.
# Used as: normalized = normalize_org_type(raw_org_type)

ORG_TYPE_MAP: dict[str, OrgType] = {
    # company variants
    "company": OrgType.COMPANY,
    "corporation": OrgType.COMPANY,
    "corp": OrgType.COMPANY,
    "firm": OrgType.COMPANY,
    "business": OrgType.COMPANY,
    "bank": OrgType.COMPANY,
    "utility": OrgType.COMPANY,
    "energy company": OrgType.COMPANY,
    "financial institution": OrgType.COMPANY,
    "investment bank": OrgType.COMPANY,
    "law firm": OrgType.COMPANY,
    "consulting firm": OrgType.COMPANY,
    "accounting firm": OrgType.COMPANY,
    "insurance company": OrgType.COMPANY,
    "media company": OrgType.COMPANY,
    "technology company": OrgType.COMPANY,
    "telecommunications company": OrgType.COMPANY,
    "pipeline company": OrgType.COMPANY,
    "trading company": OrgType.COMPANY,
    "power company": OrgType.COMPANY,
    "subsidiary": OrgType.COMPANY,
    "joint venture": OrgType.COMPANY,
    "partnership": OrgType.COMPANY,

    # government variants
    "government": OrgType.GOVERNMENT,
    "government body": OrgType.GOVERNMENT,
    "government agency": OrgType.GOVERNMENT,
    "regulatory body": OrgType.GOVERNMENT,
    "regulatory agency": OrgType.GOVERNMENT,
    "regulator": OrgType.GOVERNMENT,
    "federal agency": OrgType.GOVERNMENT,
    "state agency": OrgType.GOVERNMENT,
    "commission": OrgType.GOVERNMENT,
    "legislature": OrgType.GOVERNMENT,
    "court": OrgType.GOVERNMENT,
    "municipality": OrgType.GOVERNMENT,
    "political party": OrgType.GOVERNMENT,

    # nonprofit variants
    "nonprofit": OrgType.NONPROFIT,
    "non-profit": OrgType.NONPROFIT,
    "ngo": OrgType.NONPROFIT,
    "trade association": OrgType.NONPROFIT,
    "industry group": OrgType.NONPROFIT,
    "professional association": OrgType.NONPROFIT,
    "foundation": OrgType.NONPROFIT,
    "charity": OrgType.NONPROFIT,

    # university variants
    "university": OrgType.UNIVERSITY,
    "educational institution": OrgType.UNIVERSITY,
    "school": OrgType.UNIVERSITY,
    "college": OrgType.UNIVERSITY,
    "research institution": OrgType.UNIVERSITY,

    # internal division variants
    "internal division": OrgType.INTERNAL_DIVISION,
    "internal department": OrgType.INTERNAL_DIVISION,
    "division": OrgType.INTERNAL_DIVISION,
    "department": OrgType.INTERNAL_DIVISION,
    "business unit": OrgType.INTERNAL_DIVISION,
    "group": OrgType.INTERNAL_DIVISION,
    "team": OrgType.INTERNAL_DIVISION,
    "desk": OrgType.INTERNAL_DIVISION,
    "unit": OrgType.INTERNAL_DIVISION,
}


def normalize_org_type(raw: str | None) -> OrgType | None:
    """
    Map a free-text org_type to one of 6 normalized categories.

    Returns None only if raw is None. Unknown strings map to OTHER.
    """
    if raw is None:
        return None
    key = raw.strip().lower()
    return ORG_TYPE_MAP.get(key, OrgType.OTHER)