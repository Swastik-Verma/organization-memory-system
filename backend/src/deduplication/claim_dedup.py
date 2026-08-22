"""
Claim deduplication — merge duplicate facts, detect conflicts.

After entity resolution, multiple extracted relationships may assert
the same fact (same subject, same type, same object). This module:

  1. Resolves person names to canonical IDs
  2. Normalizes symmetric relationships (works_with, negotiating_with)
  3. Groups by dedup key: (subject_id, type, object_id)
  4. Merges each group into one DedupedClaim with accumulated Evidence
  5. Detects conflicts: same (subject_id, type) + different object_id

The output is ready for Neo4j ingestion:
  - One Claim node per unique fact
  - Multiple Evidence nodes per claim (one per supporting email)
  - SUPPORTED_BY edges connecting them
"""

import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Relationship type classification
# ---------------------------------------------------------------------------

# Symmetric: "A works_with B" = "B works_with A" → sort pair alphabetically
SYMMETRIC_TYPES = frozenset({"works_with", "negotiating_with"})

# Asymmetric: direction matters, "A reports_to B" ≠ "B reports_to A"
ASYMMETRIC_TYPES = frozenset({"reports_to", "requests_from", "informs"})

# Those for which there can be conflict
EXCLUSIVE_TYPES = frozenset({"reports_to"})

ALL_RELATIONSHIP_TYPES = SYMMETRIC_TYPES | ASYMMETRIC_TYPES


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EvidenceItem:
    """One piece of evidence supporting a claim (from one email)."""
    message_id: str
    quote: str
    char_start: int | None
    char_end: int | None
    evidence_verified: bool | None
    confidence: float
    email_date: str | None       # date of the source email

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DedupedClaim:
    """A single fact with all its supporting evidence merged."""
    claim_id: str
    claim_type: str               # one of 5 relationship types
    subject_id: str               # canonical person ID (resolved)
    object_id: str                # canonical person ID (resolved)
    subject_name: str             # canonical name for display
    object_name: str
    description: str              # "Steven Kean reports_to Kenneth Lay"
    evidence: list[EvidenceItem] = field(default_factory=list)
    confidence: float = 0.0       # max confidence across evidence
    valid_from: str | None = None # earliest email date
    valid_to: str | None = None   # null = still true (Day 19 may close it)
    mention_count: int = 0        # number of supporting emails
    status: str = "current"       # current / superseded / review / archived

    def to_dict(self) -> dict:
        d = asdict(self)
        d["evidence"] = [e.to_dict() for e in self.evidence]
        return d


@dataclass
class ClaimConflict:
    """A detected conflict: same subject+type, different objects."""
    conflict_id: str
    claim_type: str
    subject_id: str
    subject_name: str
    claims: list[dict]            # summaries of the conflicting claims
    conflict_type: str = "potential"  # Day 19 classifies further

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _make_claim_id(subject_id: str, claim_type: str, object_id: str) -> str:
    """Deterministic claim ID from the fact it represents.

    Same fact always produces the same ID regardless of how many
    emails mention it. This makes Neo4j MERGE idempotent.
    """
    key = f"{subject_id}|{claim_type}|{object_id}"
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"claim:{h}"


def _make_conflict_id(subject_id: str, claim_type: str) -> str:
    key = f"conflict:{subject_id}|{claim_type}"
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"conflict:{h}"


def _resolve_name(name: str, resolution_map: dict[str, str]) -> str:
    """Resolve a person name to its canonical ID.

    Falls back to a generated ID if name is not in the map
    (can happen for names that only appear in relationships,
    never in people lists).
    """
    if not name:
        return ""
    name = name.strip()
    if name in resolution_map:
        return resolution_map[name]
    # Fallback: generate a pseudo-ID from the name
    slug = name.lower().replace(" ", "-").replace(",", "").replace(".", "")
    return f"person:{slug}:unresolved"


def _get_canonical_name(
    canonical_id: str, canonical_entities: dict[str, dict]
) -> str:
    """Get the display name for a canonical entity ID."""
    if canonical_id in canonical_entities:
        return canonical_entities[canonical_id].get("canonical_name", canonical_id)
    # For unresolved IDs, extract the name from the ID
    return canonical_id.replace("person:", "").replace("-", " ").title()


def _normalize_pair(
    subject_id: str,
    object_id: str,
    claim_type: str,
) -> tuple[str, str]:
    """For symmetric types, sort the pair so A-B and B-A produce the same key."""
    if claim_type in SYMMETRIC_TYPES:
        return tuple(sorted([subject_id, object_id]))
    return (subject_id, object_id)


def deduplicate_claims(
    extractions: list[dict],
    email_dates: dict[str, str | None],
    resolution_map: dict[str, str],
    canonical_entities: dict[str, dict],
    duplicate_ids: set[str] | None = None,
) -> tuple[list[DedupedClaim], list[ClaimConflict]]:
    """Deduplicate relationship claims across all extractions.

    Args:
        extractions:        list of extraction dicts from extractions_final.jsonl
        email_dates:        message_id → date string (from extraction_subset.jsonl)
        resolution_map:     name → canonical_id (from Days 16-17)
        canonical_entities: canonical_id → entity dict (for display names)
        duplicate_ids:      message_ids to skip (from Day 15), or None

    Returns:
        (deduped_claims, conflicts)
    """
    duplicate_ids = duplicate_ids or set()

    # ------------------------------------------------------------------
    # Phase 1: Collect all relationships with resolved IDs
    # ------------------------------------------------------------------

    # Group by dedup key: (subject_id, type, object_id) → list of evidence
    claim_groups: dict[tuple[str, str, str], list[EvidenceItem]] = defaultdict(list)

    total_rels = 0
    skipped_rels = 0

    for extraction in extractions:
        msg_id = extraction["message_id"]

        # Skip duplicate emails
        if msg_id in duplicate_ids:
            continue

        email_date = email_dates.get(msg_id)

        for rel in extraction.get("relationships", []):
            # Skip non-approved relationships
            if rel.get("status") != "approved":
                skipped_rels += 1
                continue

            total_rels += 1

            person_a = (rel.get("person_a") or "").strip()
            person_b = (rel.get("person_b") or "").strip()
            rel_type = rel.get("relationship_type", "")

            if not person_a or not person_b or not rel_type:
                skipped_rels += 1
                continue

            if rel_type not in ALL_RELATIONSHIP_TYPES:
                skipped_rels += 1
                continue

            # Resolve to canonical IDs
            subject_id = _resolve_name(person_a, resolution_map)
            object_id = _resolve_name(person_b, resolution_map)

            # Normalize symmetric pairs
            subject_id, object_id = _normalize_pair(
                subject_id, object_id, rel_type
            )

            # Build evidence item
            evidence = EvidenceItem(
                message_id=msg_id,
                quote=rel.get("evidence") or "",
                char_start=rel.get("char_start"),
                char_end=rel.get("char_end"),
                evidence_verified=rel.get("evidence_verified"),
                confidence=rel.get("confidence", 0.5),
                email_date=email_date,
            )

            key = (subject_id, rel_type, object_id)
            claim_groups[key].append(evidence)

    logger.info(
        "Collected %d approved relationships (%d skipped) → %d unique facts",
        total_rels, skipped_rels, len(claim_groups),
    )

    # ------------------------------------------------------------------
    # Phase 2: Build deduplicated claims
    # ------------------------------------------------------------------

    deduped_claims: list[DedupedClaim] = []

    for (subject_id, claim_type, object_id), evidence_items in claim_groups.items():
        claim_id = _make_claim_id(subject_id, claim_type, object_id)

        subject_name = _get_canonical_name(subject_id, canonical_entities)
        object_name = _get_canonical_name(object_id, canonical_entities)

        # Max confidence across all evidence
        max_confidence = max(e.confidence for e in evidence_items)

        # Earliest and latest dates
        dates = [
            e.email_date for e in evidence_items
            if e.email_date is not None
        ]
        dates.sort()
        valid_from = dates[0] if dates else None
        latest_date = dates[-1] if dates else None

        # Sort evidence chronologically
        evidence_items.sort(
            key=lambda e: e.email_date or "9999-12-31"
        )

        claim = DedupedClaim(
            claim_id=claim_id,
            claim_type=claim_type,
            subject_id=subject_id,
            object_id=object_id,
            subject_name=subject_name,
            object_name=object_name,
            description=f"{subject_name} {claim_type} {object_name}",
            evidence=evidence_items,
            confidence=max_confidence,
            valid_from=valid_from,
            valid_to=None,  # Day 19 may close this
            mention_count=len(evidence_items),
        )
        deduped_claims.append(claim)

    # Sort by mention count (most-mentioned facts first)
    deduped_claims.sort(key=lambda c: c.mention_count, reverse=True)

    logger.info(
        "Built %d deduplicated claims from %d relationships",
        len(deduped_claims), total_rels,
    )

    # ------------------------------------------------------------------
    # Phase 3: Detect conflicts
    # ------------------------------------------------------------------

    conflicts = detect_conflicts(deduped_claims)

    return deduped_claims, conflicts


def detect_conflicts(claims: list[DedupedClaim]) -> list[ClaimConflict]:
    """Detect conflicts: same subject + same asymmetric type + different objects.

    For symmetric types (works_with, negotiating_with), having multiple
    objects is NORMAL — a person works with many people. No conflict.

    For asymmetric types (reports_to, requests_from, informs), having
    multiple different objects for the same subject MAY indicate:
      - A temporal change (reported to X, now reports to Y)
      - A genuine contradiction
    Day 19 will classify further. Day 18 just detects and flags.
    """
    # Group by (subject_id, type) for asymmetric types only
    subject_type_groups: dict[tuple[str, str], list[DedupedClaim]] = defaultdict(list)

    for claim in claims:
        if claim.claim_type not in EXCLUSIVE_TYPES:
            continue
        key = (claim.subject_id, claim.claim_type)
        subject_type_groups[key].append(claim)

    conflicts = []
    for (subject_id, claim_type), group_claims in subject_type_groups.items():
        if len(group_claims) < 2:
            continue  # only one object — no conflict

        # Multiple different objects for the same subject + type
        conflict_id = _make_conflict_id(subject_id, claim_type)
        subject_name = group_claims[0].subject_name

        conflict = ClaimConflict(
            conflict_id=conflict_id,
            claim_type=claim_type,
            subject_id=subject_id,
            subject_name=subject_name,
            claims=[
                {
                    "claim_id": c.claim_id,
                    "object_id": c.object_id,
                    "object_name": c.object_name,
                    "mention_count": c.mention_count,
                    "valid_from": c.valid_from,
                    "confidence": c.confidence,
                }
                for c in sorted(group_claims, key=lambda x: x.valid_from or "9999")
            ],
        )
        conflicts.append(conflict)

    # Sort by number of conflicting claims (most complex first)
    conflicts.sort(key=lambda c: len(c.claims), reverse=True)

    logger.info("Detected %d potential conflicts", len(conflicts))
    return conflicts