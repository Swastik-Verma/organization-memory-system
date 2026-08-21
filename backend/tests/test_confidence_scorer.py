# tests/test_confidence_scorer.py
import pytest
from src.extraction.confidence_scorer import (
    score_evidence,
    PENALTY_EVIDENCE_UNVERIFIED,
    PENALTY_EVIDENCE_EMPTY,
    PENALTY_QUOTE_VERY_SHORT,
    PENALTY_QUOTE_SHORT,
    PENALTY_MISSING_ENDPOINT,
    PENALTY_NO_EMAIL,
    CONFIDENCE_FLOOR,
)


class TestScoreEvidence:
    def test_perfect_score(self):
        """Verified evidence, long quote, no issues → 1.0"""
        item = {
            "evidence": "John will take over the Williams contract effective Monday next week",
            "evidence_verified": True,
            "char_start": 10,
            "char_end": 75,
        }
        result = score_evidence(item, noise_regions=[], field_type="relationships")
        assert result["confidence"] == 1.0
        assert result["penalties"] == []

    def test_unverified_evidence(self):
        item = {
            "evidence": "some reasonably long quote that did not match the body",
            "evidence_verified": False,
            "char_start": None,
            "char_end": None,
        }
        result = score_evidence(item, noise_regions=[], field_type="relationships")
        assert result["confidence"] == round(1.0 - PENALTY_EVIDENCE_UNVERIFIED, 2)
        assert any(p[0] == "unverified_evidence" for p in result["penalties"])

    def test_empty_evidence_in_relationships(self):
        item = {"evidence": "", "evidence_verified": None}
        result = score_evidence(item, noise_regions=[], field_type="relationships")
        assert result["confidence"] == round(1.0 - PENALTY_EVIDENCE_EMPTY, 2)

    def test_very_short_quote(self):
        item = {
            "evidence": "John Arnold",
            "evidence_verified": True,
            "char_start": 5,
            "char_end": 15,
        }
        result = score_evidence(item, noise_regions=[], field_type="relationships")
        assert result["confidence"] == round(1.0 - PENALTY_QUOTE_VERY_SHORT, 2)

    def test_short_quote(self):
        item = {
            "evidence": "John Arnold at Enron Trading",
            "evidence_verified": True,
            "char_start": 5,
            "char_end": 32,
        }
        result = score_evidence(item, noise_regions=[], field_type="relationships")
        assert result["confidence"] == round(1.0 - PENALTY_QUOTE_SHORT, 2)

    def test_multiple_penalties_stack(self):
        """Unverified + very short → both penalties apply"""
        item = {
            "evidence": "John",
            "evidence_verified": False,
            "char_start": None,
            "char_end": None,
        }
        result = score_evidence(item, noise_regions=[], field_type="relationships")
        expected = round(1.0 - PENALTY_EVIDENCE_UNVERIFIED - PENALTY_QUOTE_VERY_SHORT, 2)
        assert result["confidence"] == expected
        assert len(result["penalties"]) == 2

    def test_floor_enforced(self):
        """Score with maximum penalties should still be >= floor"""
        item = {
            "evidence": "",
            "evidence_verified": False,
            "source": "",
            "target": "",
            "email": "",
        }
        result = score_evidence(item, noise_regions=[], field_type="relationships")
        # Max penalties: empty_evidence(0.50) + missing_endpoint(0.20) + no_email(0.05) = 0.75
        # Score: 1.0 - 0.75 = 0.25
        assert result["confidence"] == 0.25
        assert result["confidence"] >= CONFIDENCE_FLOOR

    def test_in_noise_region(self):
        from src.parsing.noise_detector import NoiseRegion
        
        # Fixed: Changed `noise_type` to `region_type`
        noise_regions = [NoiseRegion(start=0, end=100, region_type="forward_header")]
        
        item = {
            "evidence": "a quote that is long enough to not trigger short penalty here",
            "evidence_verified": True,
            "char_start": 10,
            "char_end": 50,
        }
        result = score_evidence(item, noise_regions=noise_regions, field_type="relationships")
        assert any(p[0] == "in_noise_region" for p in result["penalties"])

    def test_no_email_penalty(self):
        item = {
            "evidence": "a quote that is long enough to avoid short quote penalty here",
            "evidence_verified": True,
            "char_start": 0,
            "char_end": 60,
            "email": "",
        }
        result = score_evidence(item, noise_regions=[], field_type="relationships")
        assert any(p[0] == "no_email" for p in result["penalties"])

    def test_missing_relationship_endpoint(self):
        item = {
            "evidence": "a quote that is long enough for this test case to work properly",
            "evidence_verified": True,
            "char_start": 0,
            "char_end": 60,
            "source": "Steven Kean",
            "target": "",
        }
        result = score_evidence(item, noise_regions=[], field_type="relationships")
        assert any(p[0] == "missing_endpoint" for p in result["penalties"])

    def test_no_penalty_for_empty_evidence_on_people(self):
        """People field has no evidence by design — should not get empty_evidence penalty"""
        item = {
            "evidence": "",
            "email": "steven.kean@enron.com",
        }
        result = score_evidence(item, noise_regions=[], field_type="people")
        assert result["confidence"] == 0.90
        assert not any(p[0] == "empty_evidence" for p in result["penalties"])
        assert any(p[0] == "no_evidence_available" for p in result["penalties"])

    def test_relationships_still_penalized_for_empty_evidence(self):
        """Relationships should have evidence — empty is still a real problem"""
        item = {
            "evidence": "",
            "source": "Steven Kean",
            "target": "Ken Lay",
        }
        result = score_evidence(item, noise_regions=[], field_type="relationships")
        assert any(p[0] == "empty_evidence" for p in result["penalties"])

    def test_people_with_no_email_gets_both_penalties(self):
        """People: no_evidence_available + no_email should stack"""
        item = {
            "evidence": "",
            "email": "",
        }
        result = score_evidence(item, noise_regions=[], field_type="people")
        assert result["confidence"] == 0.85
        assert any(p[0] == "no_evidence_available" for p in result["penalties"])
        assert any(p[0] == "no_email" for p in result["penalties"])

    def test_organizations_get_baseline_penalty_only(self):
        """Orgs with no special issues get just the no_evidence_available penalty"""
        item = {
            "evidence": "",
        }
        result = score_evidence(item, noise_regions=[], field_type="organizations")
        assert result["confidence"] == 0.90
        assert len(result["penalties"]) == 1