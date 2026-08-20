"""
backend/src/graph/schema.py

Pydantic models representing every node type in the Neo4j knowledge graph.
These are used for validation before writing to the database — not the
extraction schema (backend/src/extraction/schema.py), which is what the
LLM returns. These models represent the final, clean graph-ready form.
"""

from __future__ import annotations
from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import hashlib
import json


# ---------------------------------------------------------------------------
# Enums — closed vocabularies enforced at the Python layer
# ---------------------------------------------------------------------------

class EntityType(str, Enum):
    PERSON = "Person"
    ORGANIZATION = "Organization"
    DEAL = "Deal"
    DECISION = "Decision"


class ClaimType(str, Enum):
    REPORTS_TO = "reports_to"
    WORKS_WITH = "works_with"
    REQUESTS_FROM = "requests_from"
    NEGOTIATING_WITH = "negotiating_with"
    INFORMS = "informs"


class ClaimStatus(str, Enum):
    CURRENT = "current"
    SUPERSEDED = "superseded"
    REVIEW = "review"
    ARCHIVED = "archived"


class OrgType(str, Enum):
    COMPANY = "company"
    GOVERNMENT = "government"
    NONPROFIT = "nonprofit"
    UNIVERSITY = "university"
    INTERNAL_DIVISION = "internal_division"
    OTHER = "other"


class AccessLevel(str, Enum):
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    PUBLIC = "public"


# ---------------------------------------------------------------------------
# Entity nodes
# ---------------------------------------------------------------------------

class GraphPerson(BaseModel):
    """
    A canonical person entity. One node per real person regardless of
    how many name variants appear across emails. Aliases accumulate
    during entity canonicalization (Week 3).
    """
    id: str                                        # e.g. "person:steven-kean"
    canonical_name: str                            # agreed correct name after dedup
    aliases: list[str] = Field(default_factory=list)   # every name variant seen
    emails: list[str] = Field(default_factory=list)    # every email address seen
    first_seen: Optional[date] = None             # date of earliest email mentioning them
    last_seen: Optional[date] = None              # date of most recent email mentioning them
    is_deleted: bool = False
    deleted_at: Optional[date] = None
    deletion_reason: Optional[str] = None

    @staticmethod
    def make_id(canonical_name: str) -> str:
        slug = canonical_name.lower().strip().replace(" ", "-")
        return f"person:{slug}"


class GraphOrganization(BaseModel):
    """
    A canonical organization entity. org_type is normalized to a closed
    set here — the LLM produces free-text (100+ variants); we normalize
    at ingestion.
    """
    id: str                                        # e.g. "org:enron-corp"
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    org_type: OrgType = OrgType.OTHER             # normalized closed set
    first_seen: Optional[date] = None
    last_seen: Optional[date] = None
    is_deleted: bool = False
    deleted_at: Optional[date] = None
    deletion_reason: Optional[str] = None

    @staticmethod
    def make_id(canonical_name: str) -> str:
        slug = canonical_name.lower().strip().replace(" ", "-")
        return f"org:{slug}"


class GraphDeal(BaseModel):
    """
    A business transaction or contract referenced across emails.
    Deals are entity nodes (not claims) because they are referenced
    repeatedly and have their own identity across time.
    """
    id: str                                        # e.g. "deal:pge-500mw-purchase"
    name: str
    status: Optional[str] = None                  # e.g. "negotiating", "closed", "cancelled"
    party_ids: list[str] = Field(default_factory=list)  # ids of Person/Org nodes
    first_seen: Optional[date] = None
    last_seen: Optional[date] = None
    is_deleted: bool = False

    @staticmethod
    def make_id(name: str) -> str:
        slug = name.lower().strip()[:60].replace(" ", "-")
        return f"deal:{slug}"


class GraphDecision(BaseModel):
    """
    An action or choice stated in an email. made_by and affects edges
    are stored as graph relationships, not as fields here. affects_unresolved
    holds strings that didn't match any known entity — stored as text to
    avoid creating fake hub nodes (see PROJECT_CONTEXT §9.1).
    """
    id: str                                        # deterministic hash
    description: str
    affects_unresolved: list[str] = Field(default_factory=list)
    is_deleted: bool = False

    @staticmethod
    def make_id(message_id: str, description: str) -> str:
        raw = f"{message_id}::{description}"
        return "decision:" + hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Claim node
# ---------------------------------------------------------------------------

class GraphClaim(BaseModel):
    """
    A reified relationship between two entities. Sits as a node between
    subject and object so that evidence, validity windows, supersession
    links, and confidence scores can all attach to it.

    Why a node and not a direct edge: a Neo4j relationship cannot be the
    endpoint of another relationship — so evidence, supersession, and
    conflict links have nowhere to attach on a bare edge. Reifying the
    claim as a node solves this cleanly.
    """
    id: str                                        # deterministic hash
    type: ClaimType
    description: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    valid_from: Optional[date] = None             # = date of source email
    valid_to: Optional[date] = None               # null means still current
    status: ClaimStatus = ClaimStatus.CURRENT
    extraction_version: str = "v2/gemini-3.1-flash-lite"
    access_level: AccessLevel = AccessLevel.INTERNAL
    is_deleted: bool = False
    deleted_at: Optional[date] = None
    deletion_reason: Optional[str] = None

    @staticmethod
    def make_id(message_id: str, claim_type: str,
                subject_id: str, object_id: str, quote: str) -> str:
        raw = f"{message_id}::{claim_type}::{subject_id}::{object_id}::{quote}"
        return "claim:" + hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Evidence node
# ---------------------------------------------------------------------------

class GraphEvidence(BaseModel):
    """
    A verbatim quote from an email body that supports a claim.
    char_start/char_end are computed by the evidence verification
    script (Days 8-11) — they point to the exact position in the
    Message body so the frontend can highlight the span.
    in_quoted_block flags evidence that came from a quoted reply
    chain rather than the original email content.
    """
    id: str                                        # deterministic hash
    quote: str
    char_start: Optional[int] = None             # filled by verification script
    char_end: Optional[int] = None
    in_quoted_block: bool = False                 # filled by noise detector

    @staticmethod
    def make_id(message_id: str, quote: str) -> str:
        raw = f"{message_id}::{quote}"
        return "evidence:" + hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Message node
# ---------------------------------------------------------------------------

class GraphMessage(BaseModel):
    """
    One email from the corpus. Stored as a node so evidence can link
    directly back to the source message — the frontend evidence panel
    renders the full body with the evidence span highlighted.
    Created for every email in the subset, even those that produced
    zero extractions, so health metrics reflect true coverage.
    """
    message_id: str                               # original RFC 2822 Message-ID
    date: Optional[date] = None                  # None for the 535 null-date emails
    subject: Optional[str] = None
    from_addr: Optional[str] = None
    body: Optional[str] = None
    x_origin: Optional[str] = None              # mailbox owner e.g. "kean-s"
    is_deleted: bool = False