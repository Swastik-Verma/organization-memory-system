import pytest
from src.extraction.quality_gate import (
    gate_item,
    check_hard_rejects,
    STATUS_APPROVED,
    STATUS_REVIEW,
    STATUS_REJECTED,
    SOFT_THRESHOLD,
    HARD_THRESHOLD,
)


class TestHardRejects:
    def test_person_missing_name(self):
        item = {"name": "", "confidence": 0.95}
        assert check_hard_rejects(item, "people") == "missing_name"

    def test_person_whitespace_name(self):
        item = {"name": "   ", "confidence": 0.95}
        assert check_hard_rejects(item, "people") == "missing_name"

    def test_person_valid_name_passes(self):
        item = {"name": "Steven Kean", "confidence": 0.95}
        assert check_hard_rejects(item, "people") is None

    def test_decision_missing_description(self):
        item = {"description": "", "confidence": 0.95}
        assert check_hard_rejects(item, "decisions") == "missing_description"

    def test_relationship_missing_source(self):
        item = {
            "person_a": "",
            "person_b": "Ken Lay",
            "relationship_type": "reports_to",
            "evidence": "a sufficiently long evidence quote here",
            "evidence_verified": True,
        }
        assert check_hard_rejects(item, "relationships") == "missing_source"

    def test_relationship_missing_target(self):
        item = {
            "person_a": "Steven Kean",
            "person_b": "",
            "relationship_type": "reports_to",
            "evidence": "a sufficiently long evidence quote here",
            "evidence_verified": True,
        }
        assert check_hard_rejects(item, "relationships") == "missing_target"

    def test_self_referential_relationship(self):
        item = {
            "person_a": "Steven Kean",
            "person_b": "Steven Kean",
            "relationship_type": "works_with",
            "evidence": "a sufficiently long evidence quote here",
            "evidence_verified": True,
        }
        assert check_hard_rejects(item, "relationships") == "self_referential"

    def test_self_referential_case_insensitive(self):
        item = {
            "person_a": "Steven Kean",
            "person_b": "steven kean",
            "relationship_type": "works_with",
            "evidence": "a sufficiently long evidence quote here",
            "evidence_verified": True,
        }
        assert check_hard_rejects(item, "relationships") == "self_referential"

    def test_invalid_relationship_type(self):
        item = {
            "person_a": "Steven Kean",
            "person_b": "Ken Lay",
            "relationship_type": "mentors",  # not in closed vocabulary
            "evidence": "a sufficiently long evidence quote here",
            "evidence_verified": True,
        }
        result = check_hard_rejects(item, "relationships")
        assert result.startswith("invalid_relationship_type")

    def test_unverifiable_and_too_short(self):
        item = {
            "person_a": "Steven Kean",
            "person_b": "Ken Lay",
            "relationship_type": "reports_to",
            "evidence": "short",  # < 20 chars
            "evidence_verified": False,
        }
        assert check_hard_rejects(item, "relationships") == "unverifiable_and_too_short"

    def test_relationship_missing_evidence(self):
        item = {
            "person_a": "Steven Kean",
            "person_b": "Ken Lay",
            "relationship_type": "reports_to",
            "evidence": "",
            "evidence_verified": None,
        }
        assert check_hard_rejects(item, "relationships") == "missing_evidence"

    def test_valid_relationship_passes(self):
        item = {
            "person_a": "Steven Kean",
            "person_b": "Ken Lay",
            "relationship_type": "reports_to",
            "evidence": "Steven reports directly to Ken on all matters",
            "evidence_verified": True,
        }
        assert check_hard_rejects(item, "relationships") is None


class TestGateItem:
    def test_high_confidence_approved(self):
        item = {"name": "Steven Kean", "confidence": 0.95}
        result = gate_item(item, "people")
        assert result["status"] == STATUS_APPROVED

    def test_at_soft_threshold_approved(self):
        item = {"name": "Steven Kean", "confidence": SOFT_THRESHOLD}
        result = gate_item(item, "people")
        assert result["status"] == STATUS_APPROVED

    def test_just_below_soft_threshold_review(self):
        item = {"name": "Steven Kean", "confidence": SOFT_THRESHOLD - 0.01}
        result = gate_item(item, "people")
        assert result["status"] == STATUS_REVIEW

    def test_at_hard_threshold_review(self):
        item = {"name": "Steven Kean", "confidence": HARD_THRESHOLD}
        result = gate_item(item, "people")
        assert result["status"] == STATUS_REVIEW

    def test_below_hard_threshold_rejected(self):
        item = {"name": "Steven Kean", "confidence": HARD_THRESHOLD - 0.01}
        result = gate_item(item, "people")
        assert result["status"] == STATUS_REJECTED

    def test_hard_reject_overrides_high_confidence(self):
        """Structural problems reject even with perfect confidence"""
        item = {"name": "", "confidence": 1.0}
        result = gate_item(item, "people")
        assert result["status"] == STATUS_REJECTED
        assert "hard_reject" in result["gate_reason"]

    def test_gate_reason_included(self):
        item = {"name": "Steven Kean", "confidence": 0.95}
        result = gate_item(item, "people")
        assert "gate_reason" in result
        assert result["gate_reason"] != ""