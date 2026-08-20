# # tests/test_graph_schema.py
# import pytest
# from src.graph.schema import (
#     GraphPerson, GraphOrganization, GraphClaim, 
#     GraphEvidence, GraphDecision, GraphDeal, GraphMessage
# )

# class TestGraphPerson:
#     def test_valid_creation(self):
#         p = GraphPerson(canonical_name="Steven Kean", emails=["steven.kean@enron.com"])
#         assert p.canonical_name == "Steven Kean"
#         assert p.is_deleted is False
#         assert p.aliases == []

#     def test_deterministic_id(self):
#         id1 = GraphPerson.make_id("Steven Kean")
#         id2 = GraphPerson.make_id("Steven Kean")
#         assert id1 == id2

#     def test_id_prefix(self):
#         pid = GraphPerson.make_id("Steven Kean")
#         assert pid.startswith("person:")

#     def test_case_insensitive_id(self):
#         id1 = GraphPerson.make_id("Steven Kean")
#         id2 = GraphPerson.make_id("steven kean")
#         assert id1 == id2  # slugification should normalize case

#     def test_id_different_for_different_names(self):
#         id1 = GraphPerson.make_id("Steven Kean")
#         id2 = GraphPerson.make_id("Vince Kaminski")
#         assert id1 != id2


# class TestGraphClaim:
#     def test_deterministic_hash_id(self):
#         id1 = GraphClaim.make_id(
#             message_id="<abc@enron.com>",
#             claim_type="reports_to",
#             subject_id="person:steven-kean",
#             object_id="person:ken-lay",
#             quote="Steven reports directly to Ken"
#         )
#         id2 = GraphClaim.make_id(
#             message_id="<abc@enron.com>",
#             claim_type="reports_to",
#             subject_id="person:steven-kean",
#             object_id="person:ken-lay",
#             quote="Steven reports directly to Ken"
#         )
#         assert id1 == id2
#         assert id1.startswith("claim:")

#     def test_different_inputs_different_id(self):
#         id1 = GraphClaim.make_id("<abc@enron.com>", "reports_to", "a", "b", "quote1")
#         id2 = GraphClaim.make_id("<xyz@enron.com>", "reports_to", "a", "b", "quote1")
#         assert id1 != id2

#     def test_null_temporal_fields(self):
#         c = GraphClaim(
#             id="claim:abc123",
#             type="reports_to",
#             description="Test",
#             confidence=0.8,
#             valid_from=None,
#             valid_to=None,
#             status="current"
#         )
#         assert c.valid_from is None
#         assert c.valid_to is None


# class TestGraphEvidence:
#     def test_char_offsets_optional(self):
#         e = GraphEvidence(
#             id="evidence:abc",
#             quote="some quote",
#             char_start=None,
#             char_end=None,
#             in_quoted_block=False
#         )
#         assert e.char_start is None

import pytest
from src.graph.schema import (
    GraphClaim,
    GraphDeal,
    GraphDecision,
    GraphEvidence,
    GraphMessage,
    GraphOrganization,
    GraphPerson,
)


class TestGraphPerson:

    def test_valid_creation(self):
        pid = GraphPerson.make_id("Steven Kean")
        p = GraphPerson(
            id=pid,
            canonical_name="Steven Kean",
            emails=["steven.kean@enron.com"],
        )
        assert p.canonical_name == "Steven Kean"
        assert p.is_deleted is False
        assert p.aliases == []

    def test_deterministic_id(self):
        id1 = GraphPerson.make_id("Steven Kean")
        id2 = GraphPerson.make_id("Steven Kean")
        assert id1 == id2

    def test_id_prefix(self):
        pid = GraphPerson.make_id("Steven Kean")
        assert pid.startswith("person:")

    def test_case_insensitive_id(self):
        id1 = GraphPerson.make_id("Steven Kean")
        id2 = GraphPerson.make_id("steven kean")
        assert id1 == id2

    def test_id_different_for_different_names(self):
        id1 = GraphPerson.make_id("Steven Kean")
        id2 = GraphPerson.make_id("Vince Kaminski")
        assert id1 != id2


class TestGraphClaim:

    def test_deterministic_hash_id(self):
        # Corrected parameter names: subject_id and object_id
        id1 = GraphClaim.make_id(
            message_id="<abc@enron.com>",
            claim_type="reports_to",
            subject_id="person:steven-kean",
            object_id="person:ken-lay",
            quote="Steven reports directly to Ken",
        )
        id2 = GraphClaim.make_id(
            message_id="<abc@enron.com>",
            claim_type="reports_to",
            subject_id="person:steven-kean",
            object_id="person:ken-lay",
            quote="Steven reports directly to Ken",
        )
        assert id1 == id2
        assert id1.startswith("claim:")

    def test_different_inputs_different_id(self):
        id1 = GraphClaim.make_id(
            "<abc@enron.com>", "reports_to", "a", "b", "quote1"
        )
        id2 = GraphClaim.make_id(
            "<xyz@enron.com>", "reports_to", "a", "b", "quote1"
        )
        assert id1 != id2

    def test_null_temporal_fields(self):
        c = GraphClaim(
            id="claim:abc123",
            type="reports_to",
            description="Test",
            confidence=0.8,
            valid_from=None,
            valid_to=None,
            status="current",
        )
        assert c.valid_from is None
        assert c.valid_to is None


class TestGraphEvidence:

    def test_char_offsets_optional(self):
        e = GraphEvidence(
            id="evidence:abc",
            quote="some quote",
            char_start=None,
            char_end=None,
            in_quoted_block=False,
        )
        assert e.char_start is None

    def test_evidence_make_id(self):
        eid = GraphEvidence.make_id("<abc@enron.com>", "some quote")
        assert eid.startswith("evidence:")


class TestGraphOrganization:

    def test_valid_creation_and_make_id(self):
        org_id = GraphOrganization.make_id("Enron Corp")
        org = GraphOrganization(id=org_id, canonical_name="Enron Corp")
        assert org.id == "org:enron-corp"
        assert org.is_deleted is False


class TestGraphDeal:

    def test_make_id_truncation(self):
        long_name = "A" * 70
        deal_id = GraphDeal.make_id(long_name)
        assert len(deal_id.replace("deal:", "")) == 60


class TestGraphDecision:

    def test_deterministic_hash_id(self):
        id1 = GraphDecision.make_id("<msg1@enron.com>", "Approve budget")
        id2 = GraphDecision.make_id("<msg1@enron.com>", "Approve budget")
        assert id1 == id2
        assert id1.startswith("decision:")


class TestGraphMessage:

    def test_valid_creation(self):
        msg = GraphMessage(
            message_id="<msg1@enron.com>", subject="Project Update"
        )
        assert msg.message_id == "<msg1@enron.com>"
        assert msg.date is None