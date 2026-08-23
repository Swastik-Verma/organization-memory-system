"""
Unit tests for conflict resolution (Day 19).

Tests classification (exclusive vs non-exclusive, temporal vs contradiction),
auto-resolution of validity windows, review queue routing, and reversal detection.
"""

import pytest
from src.deduplication.conflict_resolver import (
    classify_conflict,
    resolve_conflicts,
    apply_updates,
    detect_decision_reversals,
    _date_range,
    _ranges_overlap,
    EXCLUSIVE_TYPES,
    NON_EXCLUSIVE_TYPES,
    ClaimUpdate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_claim(
    claim_id: str,
    claim_type: str = "reports_to",
    subject_id: str = "person:kean",
    object_id: str = "person:lay",
    subject_name: str = "Steven Kean",
    object_name: str = "Kenneth Lay",
    dates: list[str] | None = None,
) -> dict:
    """Build a claim dict with evidence at the given dates."""
    dates = dates or ["2001-01-15"]
    return {
        "claim_id": claim_id,
        "claim_type": claim_type,
        "subject_id": subject_id,
        "object_id": object_id,
        "subject_name": subject_name,
        "object_name": object_name,
        "description": f"{subject_name} {claim_type} {object_name}",
        "evidence": [
            {
                "message_id": f"msg-{i}",
                "quote": "some quote",
                "email_date": d,
                "confidence": 0.9,
            }
            for i, d in enumerate(dates)
        ],
        "confidence": 0.9,
        "valid_from": min(d for d in dates if d) if any(dates) else None,
        "valid_to": None,
        "mention_count": len(dates),
        "status": "current",
    }


def make_conflict(
    conflict_id: str,
    claim_type: str,
    subject_id: str,
    subject_name: str,
    claims: list[dict],
) -> dict:
    """Build a conflict dict referencing the given claims."""
    return {
        "conflict_id": conflict_id,
        "claim_type": claim_type,
        "subject_id": subject_id,
        "subject_name": subject_name,
        "claims": [
            {
                "claim_id": c["claim_id"],
                "object_id": c["object_id"],
                "object_name": c["object_name"],
                "mention_count": c["mention_count"],
                "valid_from": c["valid_from"],
                "confidence": c["confidence"],
            }
            for c in claims
        ],
    }


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

class TestDateRange:
    def test_single_date(self):
        claim = make_claim("c1", dates=["2001-01-15"])
        assert _date_range(claim) == ("2001-01-15", "2001-01-15")

    def test_multiple_dates(self):
        claim = make_claim("c1", dates=["2001-03-01", "2001-01-15", "2001-06-01"])
        assert _date_range(claim) == ("2001-01-15", "2001-06-01")

    def test_no_dates(self):
        claim = make_claim("c1", dates=[None])
        assert _date_range(claim) == (None, None)


class TestRangesOverlap:
    def test_clear_overlap(self):
        assert _ranges_overlap(("2001-01-01", "2001-06-01"),
                               ("2001-03-01", "2001-09-01")) is True

    def test_no_overlap(self):
        assert _ranges_overlap(("2001-01-01", "2001-03-01"),
                               ("2001-06-01", "2001-09-01")) is False

    def test_touching_ranges_overlap(self):
        """Ranges that share an endpoint count as overlapping."""
        assert _ranges_overlap(("2001-01-01", "2001-06-01"),
                               ("2001-06-01", "2001-09-01")) is True

    def test_contained_range(self):
        assert _ranges_overlap(("2001-01-01", "2001-12-01"),
                               ("2001-03-01", "2001-06-01")) is True

    def test_none_when_missing_dates(self):
        assert _ranges_overlap((None, None), ("2001-01-01", "2001-06-01")) is None


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class TestClassifyConflict:
    def test_non_exclusive_type_not_a_conflict(self):
        """requests_from with multiple objects is normal."""
        conflict = make_conflict("conf1", "requests_from", "person:kean",
                                 "Steven Kean", [
            make_claim("c1", claim_type="requests_from", object_id="person:a",
                       object_name="Alice", dates=["2001-01-15"]),
            make_claim("c2", claim_type="requests_from", object_id="person:b",
                       object_name="Bob", dates=["2001-03-15"]),
        ])
        classification, _ = classify_conflict(conflict, {})
        assert classification == "not_a_conflict"

    def test_informs_not_a_conflict(self):
        conflict = make_conflict("conf1", "informs", "person:kean",
                                 "Steven Kean", [
            make_claim("c1", claim_type="informs", object_id="person:a",
                       dates=["2001-01-15"]),
            make_claim("c2", claim_type="informs", object_id="person:b",
                       dates=["2001-01-20"]),
        ])
        classification, _ = classify_conflict(conflict, {})
        assert classification == "not_a_conflict"

    def test_works_with_not_a_conflict(self):
        conflict = make_conflict("conf1", "works_with", "person:kean",
                                 "Steven Kean", [
            make_claim("c1", claim_type="works_with", object_id="person:a",
                       dates=["2001-01-15"]),
            make_claim("c2", claim_type="works_with", object_id="person:b",
                       dates=["2001-01-20"]),
        ])
        classification, _ = classify_conflict(conflict, {})
        assert classification == "not_a_conflict"

    def test_temporal_succession_different_dates(self):
        """reports_to with different dates = reporting line changed."""
        conflict = make_conflict("conf1", "reports_to", "person:kean",
                                 "Steven Kean", [
            make_claim("c1", object_id="person:lay", object_name="Kenneth Lay",
                       dates=["2001-01-15"]),
            make_claim("c2", object_id="person:skilling", object_name="Jeff Skilling",
                       dates=["2001-06-01"]),
        ])
        classification, _ = classify_conflict(conflict, {})
        assert classification == "temporal_succession"

    def test_direct_contradiction_same_dates(self):
        """reports_to with same date = genuine contradiction."""
        conflict = make_conflict("conf1", "reports_to", "person:kean",
                                 "Steven Kean", [
            make_claim("c1", object_id="person:lay", object_name="Kenneth Lay",
                       dates=["2001-06-01"]),
            make_claim("c2", object_id="person:skilling", object_name="Jeff Skilling",
                       dates=["2001-06-01"]),
        ])
        classification, _ = classify_conflict(conflict, {})
        assert classification == "direct_contradiction"

    def test_undated_cannot_classify(self):
        conflict = make_conflict("conf1", "reports_to", "person:kean",
                                 "Steven Kean", [
            make_claim("c1", object_id="person:lay", dates=[None]),
            make_claim("c2", object_id="person:skilling", dates=["2001-06-01"]),
        ])
        classification, _ = classify_conflict(conflict, {})
        assert classification == "undated"

# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

class TestResolveConflicts:
    def test_non_exclusive_dismissed(self):
        c1 = make_claim("c1", claim_type="works_with", object_id="person:a")
        c2 = make_claim("c2", claim_type="works_with", object_id="person:b")
        conflict = make_conflict("conf1", "works_with", "person:kean",
                                 "Steven Kean", [c1, c2])

        resolved, updates = resolve_conflicts([conflict], [c1, c2])
        assert len(resolved) == 1
        assert resolved[0].resolution == "dismissed"
        assert len(updates) == 0  # no claims modified

    def test_temporal_succession_auto_resolved(self):
        c1 = make_claim("c1", object_id="person:lay", object_name="Kenneth Lay",
                        dates=["2001-01-15", "2001-03-01"])
        c2 = make_claim("c2", object_id="person:skilling", object_name="Jeff Skilling",
                        dates=["2001-06-01"])
        conflict = make_conflict("conf1", "reports_to", "person:kean",
                                 "Steven Kean", [c1, c2])

        resolved, updates = resolve_conflicts([conflict], [c1, c2])
        assert resolved[0].resolution == "auto_resolved"

        # c1 (earlier) should be superseded with a closed window
        assert "c1" in updates
        assert updates["c1"].status == "superseded"
        assert updates["c1"].valid_to == "2001-06-01"  # next claim's start
        assert updates["c1"].superseded_by == "c2"

        # c2 (later) should be current
        assert updates["c2"].status == "current"
        assert updates["c2"].supersedes == "c1"

    def test_three_way_temporal_chain(self):
        """Three successive claims form a supersession chain."""
        c1 = make_claim("c1", object_id="p:a", object_name="A", dates=["2001-01-01"])
        c2 = make_claim("c2", object_id="p:b", object_name="B", dates=["2001-05-01"])
        c3 = make_claim("c3", object_id="p:c", object_name="C", dates=["2001-09-01"])
        conflict = make_conflict("conf1", "reports_to", "person:kean",
                                 "Steven Kean", [c1, c2, c3])

        resolved, updates = resolve_conflicts([conflict], [c1, c2, c3])
        assert resolved[0].resolution == "auto_resolved"
        assert len(resolved[0].superseded_claim_ids) == 2
        assert resolved[0].current_claim_id == "c3"

        assert updates["c1"].valid_to == "2001-05-01"
        assert updates["c2"].valid_to == "2001-09-01"
        assert updates["c3"].valid_to is None
        assert updates["c3"].status == "current"

    def test_direct_contradiction_needs_review(self):
        """Same date on both claims = cannot determine which is current."""
        c1 = make_claim("c1", object_id="person:lay",
                        dates=["2001-06-01"])
        c2 = make_claim("c2", object_id="person:skilling",
                        dates=["2001-06-01"])
        conflict = make_conflict("conf1", "reports_to", "person:kean",
                                "Steven Kean", [c1, c2])
        resolved, updates = resolve_conflicts([conflict], [c1, c2])
        assert resolved[0].resolution == "needs_review"
        assert updates["c1"].status == "review"
        assert updates["c2"].status == "review"
        assert "c2" in updates["c1"].conflicts_with
        assert "c1" in updates["c2"].conflicts_with

    def test_undated_needs_review(self):
        c1 = make_claim("c1", object_id="person:lay", dates=[None])
        c2 = make_claim("c2", object_id="person:skilling", dates=["2001-06-01"])
        conflict = make_conflict("conf1", "reports_to", "person:kean",
                                 "Steven Kean", [c1, c2])

        resolved, _ = resolve_conflicts([conflict], [c1, c2])
        assert resolved[0].resolution == "needs_review"
        assert resolved[0].classification == "undated"

    def test_empty_conflicts(self):
        resolved, updates = resolve_conflicts([], [])
        assert len(resolved) == 0
        assert len(updates) == 0


# ---------------------------------------------------------------------------
# apply_updates
# ---------------------------------------------------------------------------

class TestApplyUpdates:
    def test_applies_valid_to_and_status(self):
        claim = make_claim("c1")
        updates = {
            "c1": ClaimUpdate(claim_id="c1", valid_to="2001-06-01",
                              status="superseded", superseded_by="c2"),
        }
        result = apply_updates([claim], updates)
        assert result[0]["valid_to"] == "2001-06-01"
        assert result[0]["status"] == "superseded"
        assert result[0]["superseded_by"] == "c2"

    def test_does_not_modify_input(self):
        claim = make_claim("c1")
        original_status = claim["status"]
        updates = {"c1": ClaimUpdate(claim_id="c1", status="superseded")}
        apply_updates([claim], updates)
        assert claim["status"] == original_status  # unchanged

    def test_unaffected_claims_get_default_fields(self):
        claim = make_claim("c1")
        result = apply_updates([claim], {})
        assert result[0]["supersedes"] is None
        assert result[0]["superseded_by"] is None
        assert result[0]["conflicts_with"] == []

    def test_conflicts_with_applied(self):
        claim = make_claim("c1")
        updates = {
            "c1": ClaimUpdate(claim_id="c1", status="review",
                              conflicts_with=["c2", "c3"]),
        }
        result = apply_updates([claim], updates)
        assert result[0]["conflicts_with"] == ["c2", "c3"]


# ---------------------------------------------------------------------------
# Decision reversal detection
# ---------------------------------------------------------------------------

class TestDetectDecisionReversals:
    def test_detects_no_longer(self):
        extractions = [{
            "message_id": "msg1",
            "decisions": [{
                "description": "We are no longer proceeding with the GE deal",
                "status": "approved",
            }],
        }]
        reversals = detect_decision_reversals(extractions)
        assert len(reversals) == 1
        assert reversals[0].matched_pattern == "no longer"

    def test_detects_cancelled(self):
        extractions = [{
            "message_id": "msg1",
            "decisions": [{
                "description": "The meeting has been cancelled",
                "status": "approved",
            }],
        }]
        reversals = detect_decision_reversals(extractions)
        assert len(reversals) == 1

    def test_ignores_normal_decisions(self):
        extractions = [{
            "message_id": "msg1",
            "decisions": [{
                "description": "Approved the budget for Q3",
                "status": "approved",
            }],
        }]
        reversals = detect_decision_reversals(extractions)
        assert len(reversals) == 0

    def test_skips_non_approved(self):
        extractions = [{
            "message_id": "msg1",
            "decisions": [{
                "description": "We are no longer proceeding",
                "status": "review",
            }],
        }]
        reversals = detect_decision_reversals(extractions)
        assert len(reversals) == 0

    def test_skips_duplicate_emails(self):
        extractions = [{
            "message_id": "dup1",
            "decisions": [{
                "description": "We are no longer proceeding",
                "status": "approved",
            }],
        }]
        reversals = detect_decision_reversals(extractions, duplicate_ids={"dup1"})
        assert len(reversals) == 0

    def test_case_insensitive(self):
        extractions = [{
            "message_id": "msg1",
            "decisions": [{
                "description": "We CANCELLED the contract",
                "status": "approved",
            }],
        }]
        reversals = detect_decision_reversals(extractions)
        assert len(reversals) == 1

    def test_handles_none_description(self):
        extractions = [{
            "message_id": "msg1",
            "decisions": [{"description": None, "status": "approved"}],
        }]
        reversals = detect_decision_reversals(extractions)
        assert len(reversals) == 0