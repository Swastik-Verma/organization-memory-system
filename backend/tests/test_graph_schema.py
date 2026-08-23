"""
Tests for Day 22 graph schema models.

Covers:
- Node model creation with valid data
- Default values and optional fields
- Enum validation (OrgType, ClaimType, ClaimStatus)
- Soft delete mixin
- org_type normalization function
- Rejection of invalid enum values
"""

import pytest
from pydantic import ValidationError

from src.graph.schema import (
    ClaimStatus,
    ClaimType,
    GraphClaim,
    GraphDecision,
    GraphDeal,
    GraphEvidence,
    GraphMessage,
    GraphOrganization,
    GraphPerson,
    OrgType,
    normalize_org_type,
)


# ============================================================
# GraphPerson
# ============================================================

class TestGraphPerson:
    def test_minimal_person(self):
        p = GraphPerson(id="person:kean-steven:steven-kean-at-enron-com", canonical_name="Steven Kean")
        assert p.id == "person:kean-steven:steven-kean-at-enron-com"
        assert p.canonical_name == "Steven Kean"
        assert p.aliases == []
        assert p.emails == []
        assert p.mention_count == 0
        assert p.is_deleted is False

    def test_full_person(self):
        p = GraphPerson(
            id="person:kean-steven:steven-kean-at-enron-com",
            canonical_name="Steven Kean",
            aliases=["Steven Kean", "Steven J Kean", "Steve Kean"],
            emails=["steven.kean@enron.com", "skean@enron.com"],
            mention_count=1052,
            first_seen="2000-01-03",
            last_seen="2002-01-09",
        )
        assert len(p.aliases) == 3
        assert len(p.emails) == 2
        assert p.mention_count == 1052

    def test_soft_delete_fields(self):
        p = GraphPerson(
            id="person:test",
            canonical_name="Test",
            is_deleted=True,
            deleted_at="2026-08-01T10:00:00",
            deletion_reason="test deletion",
        )
        assert p.is_deleted is True
        assert p.deleted_at == "2026-08-01T10:00:00"
        assert p.deletion_reason == "test deletion"


# ============================================================
# GraphOrganization
# ============================================================

class TestGraphOrganization:
    def test_minimal_org(self):
        o = GraphOrganization(id="org:enron", canonical_name="Enron")
        assert o.org_type is None
        assert o.is_deleted is False

    def test_org_with_type(self):
        o = GraphOrganization(
            id="org:enron",
            canonical_name="Enron",
            org_type=OrgType.COMPANY,
            aliases=["Enron Corp", "Enron Corporation"],
            mention_count=7098,
        )
        assert o.org_type == OrgType.COMPANY
        assert o.org_type.value == "company"

    def test_invalid_org_type_rejected(self):
        with pytest.raises(ValidationError):
            GraphOrganization(id="org:test", canonical_name="Test", org_type="banana")


# ============================================================
# GraphClaim
# ============================================================

class TestGraphClaim:
    def test_minimal_claim(self):
        c = GraphClaim(
            id="claim:5ee21f1691793660",
            claim_type=ClaimType.REPORTS_TO,
            description="Kean reports_to Lay",
            confidence=0.95,
        )
        assert c.status == ClaimStatus.CURRENT
        assert c.valid_to is None
        assert c.supersedes is None
        assert c.superseded_by is None
        assert c.conflicts_with == []
        assert c.mention_count == 1

    def test_superseded_claim(self):
        c = GraphClaim(
            id="claim:abc",
            claim_type=ClaimType.REPORTS_TO,
            description="Beck reports_to Causey",
            confidence=1.0,
            valid_from="2000-01-17",
            valid_to="2000-08-03",
            status=ClaimStatus.SUPERSEDED,
            superseded_by="claim:def",
            mention_count=12,
        )
        assert c.status == ClaimStatus.SUPERSEDED
        assert c.valid_to == "2000-08-03"
        assert c.superseded_by == "claim:def"

    def test_conflicting_claim(self):
        c = GraphClaim(
            id="claim:xyz",
            claim_type=ClaimType.REPORTS_TO,
            description="Eiben reports_to Venturatos",
            confidence=0.9,
            status=ClaimStatus.REVIEW,
            conflicts_with=["claim:uvw"],
        )
        assert c.status == ClaimStatus.REVIEW
        assert "claim:uvw" in c.conflicts_with

    def test_invalid_claim_type_rejected(self):
        with pytest.raises(ValidationError):
            GraphClaim(
                id="claim:test",
                claim_type="best_friends_with",
                description="nope",
                confidence=0.5,
            )

    def test_all_claim_types_valid(self):
        for ct in ClaimType:
            c = GraphClaim(
                id=f"claim:{ct.value}",
                claim_type=ct,
                description=f"test {ct.value}",
                confidence=0.5,
            )
            assert c.claim_type == ct


# ============================================================
# GraphEvidence
# ============================================================

class TestGraphEvidence:
    def test_minimal_evidence(self):
        e = GraphEvidence(id="evidence:abc123", quote="reports directly to")
        assert e.char_start is None
        assert e.evidence_verified is None
        assert e.is_deleted is False

    def test_full_evidence(self):
        e = GraphEvidence(
            id="evidence:abc123",
            quote="Steven Kean will report directly to Ken Lay",
            char_start=42,
            char_end=86,
            evidence_verified=True,
            confidence=1.0,
            email_date="2000-01-17",
            in_quoted_block=False,
        )
        assert e.char_start == 42
        assert e.char_end == 86
        assert e.evidence_verified is True


# ============================================================
# GraphMessage
# ============================================================

class TestGraphMessage:
    def test_minimal_message(self):
        m = GraphMessage(message_id="<abc123@enron.com>")
        assert m.date is None
        assert m.body is None
        assert m.is_deleted is False

    def test_full_message(self):
        m = GraphMessage(
            message_id="<abc123@enron.com>",
            date="2001-06-15",
            subject="Re: Meeting tomorrow",
            from_addr="steven.kean@enron.com",
            body="Hi, let's meet at 3pm.",
            x_origin="KEAN-S",
            x_folder="\\Steven_Kean\\Sent",
        )
        assert m.from_addr == "steven.kean@enron.com"
        assert m.x_origin == "KEAN-S"


# ============================================================
# GraphDeal and GraphDecision
# ============================================================

class TestGraphDeal:
    def test_minimal_deal(self):
        d = GraphDeal(id="deal:project-alpha", name="Project Alpha")
        assert d.status is None
        assert d.is_deleted is False


class TestGraphDecision:
    def test_decision_with_unresolved_affects(self):
        d = GraphDecision(
            id="decision:abc123",
            description="Move forward with vendor selection",
            made_by_name="Kenneth Lay",
            affects_unresolved=["employees", "all staff"],
        )
        assert len(d.affects_unresolved) == 2
        assert d.made_by_name == "Kenneth Lay"

    def test_decision_without_made_by(self):
        """384 decisions have null made_by — must be valid."""
        d = GraphDecision(
            id="decision:xyz",
            description="Some decision",
            made_by_name=None,
        )
        assert d.made_by_name is None


# ============================================================
# normalize_org_type
# ============================================================

class TestNormalizeOrgType:
    def test_none_returns_none(self):
        assert normalize_org_type(None) is None

    def test_known_types(self):
        assert normalize_org_type("company") == OrgType.COMPANY
        assert normalize_org_type("government body") == OrgType.GOVERNMENT
        assert normalize_org_type("university") == OrgType.UNIVERSITY
        assert normalize_org_type("nonprofit") == OrgType.NONPROFIT
        assert normalize_org_type("internal division") == OrgType.INTERNAL_DIVISION

    def test_case_insensitive(self):
        assert normalize_org_type("Company") == OrgType.COMPANY
        assert normalize_org_type("GOVERNMENT BODY") == OrgType.GOVERNMENT

    def test_strips_whitespace(self):
        assert normalize_org_type("  company  ") == OrgType.COMPANY

    def test_unknown_returns_other(self):
        assert normalize_org_type("something weird") == OrgType.OTHER
        assert normalize_org_type("") == OrgType.OTHER

    def test_variant_mappings(self):
        assert normalize_org_type("law firm") == OrgType.COMPANY
        assert normalize_org_type("regulatory agency") == OrgType.GOVERNMENT
        assert normalize_org_type("trade association") == OrgType.NONPROFIT
        assert normalize_org_type("research institution") == OrgType.UNIVERSITY
        assert normalize_org_type("business unit") == OrgType.INTERNAL_DIVISION