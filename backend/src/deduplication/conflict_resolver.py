"""
Conflict resolution — classify and resolve competing claims.

Takes the conflicts detected in Day 18 and:
  1. Filters to genuine conflicts (exclusive relationship types only)
  2. Classifies each as temporal succession or direct contradiction
  3. Auto-resolves temporal successions by closing validity windows
  4. Flags direct contradictions for human review

KEY CONCEPT — exclusive vs non-exclusive relationship types:

  reports_to      EXCLUSIVE     — you have one manager at a time
  requests_from   NON-EXCLUSIVE — you request from many people
  informs         NON-EXCLUSIVE — you inform many people
  works_with      NON-EXCLUSIVE — you work with many colleagues
  negotiating_with NON-EXCLUSIVE — you negotiate with many parties

Only exclusivity violations are real conflicts. "Alice requests_from Bob"
AND "Alice requests_from Carol" is normal, not contradictory.

KEY CONCEPT — temporal succession vs contradiction:

  Non-overlapping date ranges  → the fact CHANGED over time → auto-resolve
  Overlapping date ranges      → genuine contradiction → human review
  Missing dates                → cannot classify → human review
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Relationship type exclusivity
# ---------------------------------------------------------------------------

# A subject can only have ONE object for these types at any given time.
# Multiple objects = either a temporal change or a contradiction.
EXCLUSIVE_TYPES = frozenset({"reports_to"})

# A subject can have MANY objects for these types simultaneously.
# Multiple objects is normal, not a conflict.
NON_EXCLUSIVE_TYPES = frozenset({
    "works_with", "requests_from", "informs", "negotiating_with",
})


# Language patterns indicating an explicit reversal in a decision
REVERSAL_PATTERNS = (
    "no longer",
    "reversed",
    "reversal",
    "cancelled",
    "canceled",
    "rescind",
    "retract",
    "overturn",
    "changed our mind",
    "instead of",
    "rather than previously",
    "we will not",
    "decided against",
    "backing out",
    "call off",
    "called off",
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ResolvedConflict:
    """A conflict after classification and (possibly) resolution."""
    conflict_id: str
    claim_type: str
    subject_id: str
    subject_name: str
    classification: str          # "temporal_succession" | "direct_contradiction"
                                 # | "undated" | "not_a_conflict"
    resolution: str              # "auto_resolved" | "needs_review" | "dismissed"
    reason: str                  # human-readable explanation
    claims: list[dict] = field(default_factory=list)
    superseded_claim_ids: list[str] = field(default_factory=list)
    current_claim_id: str | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ClaimUpdate:
    """An update to apply to a claim as a result of conflict resolution."""
    claim_id: str
    valid_to: str | None = None
    status: str | None = None
    supersedes: str | None = None      # claim_id this one supersedes
    superseded_by: str | None = None   # claim_id that supersedes this one
    conflicts_with: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DecisionReversal:
    """A decision containing explicit reversal language."""
    message_id: str
    description: str
    matched_pattern: str

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _date_range(claim: dict) -> tuple[str | None, str | None]:
    """Extract (earliest_date, latest_date) from a claim's evidence.

    Uses the actual evidence dates, not just valid_from, because
    a claim supported by 5 emails spans a real time range.
    """
    dates = []
    for ev in claim.get("evidence", []):
        d = ev.get("email_date")
        if d:
            dates.append(d)
    if not dates:
        return (None, None)
    dates.sort()
    return (dates[0], dates[-1])


def _ranges_overlap(
    range_a: tuple[str | None, str | None],
    range_b: tuple[str | None, str | None],
) -> bool | None:
    """Check whether two date ranges overlap.

    Returns None if either range has no dates (cannot determine).

    Two ranges [a_start, a_end] and [b_start, b_end] overlap iff
    a_start <= b_end AND b_start <= a_end.
    """
    a_start, a_end = range_a
    b_start, b_end = range_b

    if a_start is None or a_end is None or b_start is None or b_end is None:
        return None

    return a_start <= b_end and b_start <= a_end


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_conflict(
    conflict: dict,
    claims_by_id: dict[str, dict],
) -> tuple[str, str]:
    """Classify a conflict based on valid_from dates only.

    Our data has valid_from (email date) but valid_to is always null.
    So classification is based on whether we can ORDER the claims by date.

    Returns (classification, reason).

    Classifications:
      "not_a_conflict"       — non-exclusive type
      "temporal_succession"  — claims have different dates, fact changed
      "direct_contradiction" — claims have the same date, can't order
      "undated"              — one or more claims missing date
    """
    claim_type = conflict.get("claim_type", "")

    # Non-exclusive types: multiple objects is normal
    if claim_type not in EXCLUSIVE_TYPES:
        return (
            "not_a_conflict",
            f"'{claim_type}' is non-exclusive — a subject can have multiple "
            f"objects simultaneously",
        )

    # Get valid_from dates from claim summaries
    claim_summaries = conflict.get("claims", [])
    if len(claim_summaries) < 2:
        return ("undated", "Fewer than 2 claims in this conflict")

    dates = [s.get("valid_from") for s in claim_summaries]

    # Case 3: any null dates → can't classify
    if any(d is None for d in dates):
        return (
            "undated",
            "One or more claims have no date — cannot determine "
            "temporal ordering",
        )

    # Case 2: all dates are the same → contradiction
    if len(set(dates)) == 1:
        return (
            "direct_contradiction",
            "All claims have the same date — cannot determine which is current",
        )

    # Case 1: dates are different → temporal succession
    return (
        "temporal_succession",
        "Claims have different dates — the fact changed over time",
    )


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def resolve_conflicts(
    conflicts: list[dict],
    claims: list[dict],
) -> tuple[list[ResolvedConflict], dict[str, ClaimUpdate]]:
    """Classify and resolve all conflicts.

    Args:
        conflicts: conflict dicts from Day 18's claim_conflicts.json
        claims:    deduplicated claim dicts from Day 18

    Returns:
        (resolved_conflicts, claim_updates)
        claim_updates maps claim_id → ClaimUpdate to apply
    """
    claims_by_id = {c["claim_id"]: c for c in claims}
    resolved: list[ResolvedConflict] = []
    updates: dict[str, ClaimUpdate] = {}

    for conflict in conflicts:
        classification, reason = classify_conflict(conflict, claims_by_id)

        conflict_id = conflict.get("conflict_id", "")
        claim_type = conflict.get("claim_type", "")
        subject_id = conflict.get("subject_id", "")
        subject_name = conflict.get("subject_name", "")
        claim_summaries = conflict.get("claims", [])

        # --- Case 1: Not actually a conflict ---
        if classification == "not_a_conflict":
            resolved.append(ResolvedConflict(
                conflict_id=conflict_id,
                claim_type=claim_type,
                subject_id=subject_id,
                subject_name=subject_name,
                classification=classification,
                resolution="dismissed",
                reason=reason,
                claims=claim_summaries,
            ))
            continue

        # --- Case 2: Temporal succession — AUTO-RESOLVE ---
        if classification == "temporal_succession":
            # Sort claims chronologically by valid_from
            full_claims = [
                claims_by_id[s["claim_id"]]
                for s in claim_summaries
                if s.get("claim_id") in claims_by_id
            ]
            full_claims.sort(key=lambda c: c.get("valid_from") or "9999-12-31")

            superseded_ids = []

            # For each claim except the last: close its window at the
            # start of the NEXT claim, mark superseded
            for i in range(len(full_claims) - 1):
                current = full_claims[i]
                next_claim = full_claims[i + 1]

                next_start = next_claim.get("valid_from")
                current_id = current["claim_id"]
                next_id = next_claim["claim_id"]

                updates[current_id] = ClaimUpdate(
                    claim_id=current_id,
                    valid_to=next_start,       # closes at the successor's start
                    status="superseded",
                    superseded_by=next_id,
                )
                superseded_ids.append(current_id)

                # The successor records what it supersedes
                if next_id not in updates:
                    updates[next_id] = ClaimUpdate(claim_id=next_id)
                updates[next_id].supersedes = current_id

            # The last claim stays current
            last_claim = full_claims[-1]
            last_id = last_claim["claim_id"]
            if last_id not in updates:
                updates[last_id] = ClaimUpdate(claim_id=last_id)
            updates[last_id].status = "current"
            updates[last_id].valid_to = None

            resolved.append(ResolvedConflict(
                conflict_id=conflict_id,
                claim_type=claim_type,
                subject_id=subject_id,
                subject_name=subject_name,
                classification=classification,
                resolution="auto_resolved",
                reason=reason,
                claims=claim_summaries,
                superseded_claim_ids=superseded_ids,
                current_claim_id=last_id,
            ))
            continue

        # --- Case 3 & 4: Direct contradiction or undated — NEEDS REVIEW ---
        claim_ids = [
            s["claim_id"] for s in claim_summaries if s.get("claim_id")
        ]

        # Create bidirectional CONFLICTS_WITH links
        for cid in claim_ids:
            if cid not in updates:
                updates[cid] = ClaimUpdate(claim_id=cid)
            others = [other for other in claim_ids if other != cid]
            updates[cid].conflicts_with = others
            updates[cid].status = "review"

        resolved.append(ResolvedConflict(
            conflict_id=conflict_id,
            claim_type=claim_type,
            subject_id=subject_id,
            subject_name=subject_name,
            classification=classification,
            resolution="needs_review",
            reason=reason,
            claims=claim_summaries,
        ))

    logger.info(
        "Resolved %d conflicts, producing %d claim updates",
        len(resolved), len(updates),
    )
    return resolved, updates


def apply_updates(
    claims: list[dict],
    updates: dict[str, ClaimUpdate],
) -> list[dict]:
    """Apply claim updates to the claim list.

    Returns a NEW list — does not modify the input.
    """
    result = []
    for claim in claims:
        claim = dict(claim)  # shallow copy
        cid = claim["claim_id"]

        if cid in updates:
            update = updates[cid]
            if update.valid_to is not None:
                claim["valid_to"] = update.valid_to
            if update.status is not None:
                claim["status"] = update.status
            if update.supersedes:
                claim["supersedes"] = update.supersedes
            if update.superseded_by:
                claim["superseded_by"] = update.superseded_by
            if update.conflicts_with:
                claim["conflicts_with"] = update.conflicts_with

        # Ensure these fields exist on every claim for Neo4j consistency
        claim.setdefault("supersedes", None)
        claim.setdefault("superseded_by", None)
        claim.setdefault("conflicts_with", [])

        result.append(claim)

    return result


# ---------------------------------------------------------------------------
# Decision reversal detection
# ---------------------------------------------------------------------------

def detect_decision_reversals(
    extractions: list[dict],
    duplicate_ids: set[str] | None = None,
) -> list[DecisionReversal]:
    """Find decisions containing explicit reversal language.

    These are decisions that undo a previous decision. We detect and flag
    them; linking each reversal to the specific decision it reverses would
    require semantic matching across the whole corpus and is deferred.
    """
    duplicate_ids = duplicate_ids or set()
    reversals: list[DecisionReversal] = []

    for extraction in extractions:
        msg_id = extraction["message_id"]
        if msg_id in duplicate_ids:
            continue

        for decision in extraction.get("decisions", []):
            if decision.get("status") != "approved":
                continue

            description = (decision.get("description") or "").lower()
            if not description:
                continue

            for pattern in REVERSAL_PATTERNS:
                if pattern in description:
                    reversals.append(DecisionReversal(
                        message_id=msg_id,
                        description=decision.get("description", ""),
                        matched_pattern=pattern,
                    ))
                    break  # one match per decision is enough

    logger.info("Detected %d decisions with reversal language", len(reversals))
    return reversals