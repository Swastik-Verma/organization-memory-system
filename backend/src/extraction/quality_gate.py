"""
Quality gates — route scored extractions into approved / review / rejected.

Two mechanisms:
1. Hard rejection rules — structural problems that make an item unusable
   regardless of confidence score
2. Confidence thresholds — soft floor for review, hard floor for rejection
"""

# --- Thresholds ---
SOFT_THRESHOLD = 0.70   # at or above → approved
HARD_THRESHOLD = 0.30   # below → rejected; between → review queue

# --- Closed vocabulary from v2 prompt ---
VALID_RELATIONSHIP_TYPES = {
    "reports_to",
    "works_with",
    "requests_from",
    "negotiating_with",
    "informs",
}

# --- Status constants ---
STATUS_APPROVED = "approved"
STATUS_REVIEW = "review"
STATUS_REJECTED = "rejected"


def check_hard_rejects(item: dict, field_type: str) -> str | None:
    """
    Check structural rejection rules that bypass the confidence score.
    
    Returns a rejection reason string if the item must be rejected,
    or None if it passes all structural checks.
    """
    # Rule 1: entity must have a name
    if field_type in ("people", "organizations", "deals"):
        name = item.get("name", "")
        if not name or not name.strip():
            return "missing_name"
    
    # Decision must have a description
    if field_type == "decisions":
        desc = item.get("description", "")
        if not desc or not desc.strip():
            return "missing_description"
    
    # Relationship-specific rules
    if field_type == "relationships":
        source = item.get("person_a", "")
        target = item.get("person_b", "")
        rel_type = item.get("relationship_type", "")
        evidence = item.get("evidence", "")
        verified = item.get("evidence_verified")
        
        # Rule 2: both endpoints required
        if not source or not source.strip():
            return "missing_source"
        if not target or not target.strip():
            return "missing_target"
        
        # Rule 5: no self-referential relationships
        if source.strip().lower() == target.strip().lower():
            return "self_referential"
        
        # Rule 3: type must be in closed vocabulary
        if rel_type not in VALID_RELATIONSHIP_TYPES:
            return f"invalid_relationship_type:{rel_type}"
        
        # Rule 4: no usable evidence at all
        if verified is False and len(evidence.strip()) < 20:
            return "unverifiable_and_too_short"
        
        # Relationships must have some evidence
        if not evidence or not evidence.strip():
            return "missing_evidence"
    
    return None


def gate_item(item: dict, field_type: str) -> dict:
    """
    Route a single scored item into approved / review / rejected.
    
    Returns a dict with 'status' and 'gate_reason'.
    """
    # Structural checks first — these bypass the score
    reject_reason = check_hard_rejects(item, field_type)
    if reject_reason:
        return {
            "status": STATUS_REJECTED,
            "gate_reason": f"hard_reject:{reject_reason}",
        }
    
    # Confidence-based routing
    confidence = item.get("confidence", 0.0)
    
    if confidence >= SOFT_THRESHOLD:
        return {
            "status": STATUS_APPROVED,
            "gate_reason": f"confidence_above_soft_threshold:{confidence}",
        }
    elif confidence >= HARD_THRESHOLD:
        return {
            "status": STATUS_REVIEW,
            "gate_reason": f"confidence_in_review_band:{confidence}",
        }
    else:
        return {
            "status": STATUS_REJECTED,
            "gate_reason": f"confidence_below_hard_threshold:{confidence}",
        }


def gate_extraction(extraction: dict) -> dict:
    """
    Apply quality gates to all items in one extraction.
    Adds 'status' and 'gate_reason' to each item.
    """
    for field in ["people", "organizations", "deals", "decisions", "relationships"]:
        for item in extraction.get(field, []):
            result = gate_item(item, field)
            item["status"] = result["status"]
            item["gate_reason"] = result["gate_reason"]
    
    return extraction