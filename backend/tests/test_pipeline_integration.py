"""
Integration test — verify the full enrichment pipeline produces
consistent, complete output from raw extraction + source email.
"""
import pytest
from src.extraction.evidence_verifier import verify_extraction
from src.extraction.confidence_scorer import score_extraction
from src.extraction.quality_gate import gate_extraction


def make_test_email():
    """Create a minimal source email for testing."""
    return {
        "message_id": "<test.001@enron.com>",
        "from_addr": "steven.kean@enron.com",
        "body": "Steven Kean will report directly to Ken Lay on all government affairs.",
        "date": "2001-06-15T10:00:00",
        "subject": "Org changes",
    }


def make_test_extraction():
    """Create a minimal extraction matching the test email."""
    return {
        "message_id": "<test.001@enron.com>",
        "people": [
            {"name": "Steven Kean", "email": "steven.kean@enron.com", "evidence": ""},
            {"name": "Ken Lay", "email": "ken.lay@enron.com", "evidence": ""},
        ],
        "organizations": [
            {"name": "Enron", "evidence": ""},
        ],
        "deals": [],
        "decisions": [
            {"description": "Kean to report to Lay on government affairs", 
             "evidence": ""},
        ],
        "relationships": [
            {
                "person_a": "Steven Kean",
                "person_b": "Ken Lay",
                "relationship_type": "reports_to",
                "evidence": "Steven Kean will report directly to Ken Lay on all government affairs",
            },
        ],
    }


class TestPipelineIntegration:
    def test_full_pipeline_produces_all_fields(self):
        """After all enrichment steps, every item has the expected fields."""
        source = make_test_email()
        extraction = make_test_extraction()
        
        # Step 1: Verify
        report = verify_extraction(extraction, source)
        for detail in report["details"]:
            field = detail["field"]
            idx = detail["index"]
            if idx < len(extraction.get(field, [])):
                extraction[field][idx]["char_start"] = detail["char_start"]
                extraction[field][idx]["char_end"] = detail["char_end"]
                extraction[field][idx]["evidence_verified"] = detail["verified"]
        
        # Step 2: Score
        extraction = score_extraction(extraction, source)
        
        # Step 3: Gate
        extraction = gate_extraction(extraction)
        
        # Check: every item has confidence, status, gate_reason
        for field in ["people", "organizations", "deals", 
                     "decisions", "relationships"]:
            for item in extraction.get(field, []):
                assert "confidence" in item, f"{field} item missing confidence"
                assert "status" in item, f"{field} item missing status"
                assert "gate_reason" in item, f"{field} item missing gate_reason"
    
    def test_verified_relationship_approved(self):
        """A relationship with matching evidence should be approved."""
        source = make_test_email()
        extraction = make_test_extraction()
        
        # Run pipeline
        report = verify_extraction(extraction, source)
        for detail in report["details"]:
            field = detail["field"]
            idx = detail["index"]
            if idx < len(extraction.get(field, [])):
                extraction[field][idx]["char_start"] = detail["char_start"]
                extraction[field][idx]["char_end"] = detail["char_end"]
                extraction[field][idx]["evidence_verified"] = detail["verified"]
        
        extraction = score_extraction(extraction, source)
        extraction = gate_extraction(extraction)
        
        # The relationship should be verified and approved
        rel = extraction["relationships"][0]
        assert rel.get("evidence_verified") is True
        assert rel["status"] == "approved"
        assert rel["confidence"] >= 0.7
    
    def test_people_approved_without_evidence(self):
        """People (no evidence by design) should still be approved."""
        source = make_test_email()
        extraction = make_test_extraction()
        
        report = verify_extraction(extraction, source)
        for detail in report["details"]:
            field = detail["field"]
            idx = detail["index"]
            if idx < len(extraction.get(field, [])):
                extraction[field][idx]["char_start"] = detail["char_start"]
                extraction[field][idx]["char_end"] = detail["char_end"]
                extraction[field][idx]["evidence_verified"] = detail["verified"]
        
        extraction = score_extraction(extraction, source)
        extraction = gate_extraction(extraction)
        
        for person in extraction["people"]:
            assert person["status"] == "approved"
    
    def test_self_referential_rejected(self):
        """A self-referential relationship should be hard-rejected."""
        source = make_test_email()
        extraction = {
            "message_id": "<test.001@enron.com>",
            "people": [],
            "organizations": [],
            "deals": [],
            "decisions": [],
            "relationships": [
                {
                    "person_a": "Steven Kean",
                    "person_b": "Steven Kean",
                    "relationship_type": "works_with",
                    "evidence": "Steven Kean works with various departments",
                },
            ],
        }
        
        report = verify_extraction(extraction, source)
        for detail in report["details"]:
            field = detail["field"]
            idx = detail["index"]
            if idx < len(extraction.get(field, [])):
                extraction[field][idx]["char_start"] = detail["char_start"]
                extraction[field][idx]["char_end"] = detail["char_end"]
                extraction[field][idx]["evidence_verified"] = detail["verified"]
        
        extraction = score_extraction(extraction, source)
        extraction = gate_extraction(extraction)
        
        rel = extraction["relationships"][0]
        assert rel["status"] == "rejected"
        assert "self_referential" in rel["gate_reason"]