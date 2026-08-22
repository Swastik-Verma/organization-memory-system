"""
Unit tests for claim deduplication (Day 18).

Tests dedup key generation, symmetric normalization, evidence accumulation,
conflict detection, and edge cases.
"""

import pytest
from src.deduplication.claim_dedup import (
    deduplicate_claims,
    detect_conflicts,
    DedupedClaim,
    EvidenceItem,
    _make_claim_id,
    _normalize_pair,
    _resolve_name,
    SYMMETRIC_TYPES,
    ASYMMETRIC_TYPES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_extraction(
    message_id: str,
    relationships: list[dict] | None = None,
) -> dict:
    """Build a minimal extraction dict for testing."""
    return {
        "message_id": message_id,
        "people": [],
        "organizations": [],
        "deals": [],
        "decisions": [],
        "relationships": relationships or [],
    }


def make_rel(
    person_a: str,
    person_b: str,
    rel_type: str = "reports_to",
    evidence: str = "some quote",
    confidence: float = 0.9,
    status: str = "approved",
) -> dict:
    return {
        "person_a": person_a,
        "person_b": person_b,
        "relationship_type": rel_type,
        "evidence": evidence,
        "char_start": 0,
        "char_end": len(evidence),
        "evidence_verified": True,
        "confidence": confidence,
        "status": status,
    }


# Simple resolution map for tests
TEST_RESOLUTION_MAP = {
    "Steven Kean": "person:kean",
    "Steve Kean": "person:kean",       # same person
    "Ken Lay": "person:lay",
    "Kenneth Lay": "person:lay",       # same person
    "Jeff Skilling": "person:skilling",
    "Alice Smith": "person:alice",
    "Bob Jones": "person:bob",
}

TEST_ENTITIES = {
    "person:kean": {"canonical_name": "Steven Kean"},
    "person:lay": {"canonical_name": "Kenneth Lay"},
    "person:skilling": {"canonical_name": "Jeff Skilling"},
    "person:alice": {"canonical_name": "Alice Smith"},
    "person:bob": {"canonical_name": "Bob Jones"},
}

TEST_DATES = {
    "msg1": "2001-01-15",
    "msg2": "2001-03-20",
    "msg3": "2001-06-01",
    "msg4": None,
}


# ---------------------------------------------------------------------------
# _make_claim_id
# ---------------------------------------------------------------------------

class TestMakeClaimId:
    def test_deterministic(self):
        id1 = _make_claim_id("person:kean", "reports_to", "person:lay")
        id2 = _make_claim_id("person:kean", "reports_to", "person:lay")
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        id1 = _make_claim_id("person:kean", "reports_to", "person:lay")
        id2 = _make_claim_id("person:kean", "reports_to", "person:skilling")
        assert id1 != id2

    def test_starts_with_claim_prefix(self):
        cid = _make_claim_id("a", "b", "c")
        assert cid.startswith("claim:")


# ---------------------------------------------------------------------------
# _normalize_pair (symmetric handling)
# ---------------------------------------------------------------------------

class TestNormalizePair:
    def test_symmetric_sorted(self):
        """For works_with, A-B and B-A produce the same pair."""
        pair1 = _normalize_pair("person:alice", "person:bob", "works_with")
        pair2 = _normalize_pair("person:bob", "person:alice", "works_with")
        assert pair1 == pair2

    def test_asymmetric_preserves_order(self):
        """For reports_to, A-B and B-A are DIFFERENT."""
        pair1 = _normalize_pair("person:alice", "person:bob", "reports_to")
        pair2 = _normalize_pair("person:bob", "person:alice", "reports_to")
        assert pair1 != pair2

    def test_negotiating_with_symmetric(self):
        pair1 = _normalize_pair("person:alice", "person:bob", "negotiating_with")
        pair2 = _normalize_pair("person:bob", "person:alice", "negotiating_with")
        assert pair1 == pair2


# ---------------------------------------------------------------------------
# _resolve_name
# ---------------------------------------------------------------------------

class TestResolveName:
    def test_found_in_map(self):
        assert _resolve_name("Steven Kean", TEST_RESOLUTION_MAP) == "person:kean"

    def test_alias_resolves_same(self):
        assert _resolve_name("Steve Kean", TEST_RESOLUTION_MAP) == "person:kean"

    def test_not_in_map_fallback(self):
        result = _resolve_name("Unknown Person", TEST_RESOLUTION_MAP)
        assert ":unresolved" in result

    def test_empty_name(self):
        assert _resolve_name("", TEST_RESOLUTION_MAP) == ""


# ---------------------------------------------------------------------------
# deduplicate_claims — basic merging
# ---------------------------------------------------------------------------

class TestDeduplicateClaims:
    def test_two_emails_same_fact_merge(self):
        """Two emails asserting the same relationship → one claim, two evidence."""
        extractions = [
            make_extraction("msg1", [make_rel("Steven Kean", "Ken Lay", "reports_to",
                                               evidence="Kean reports to Lay")]),
            make_extraction("msg2", [make_rel("Steve Kean", "Kenneth Lay", "reports_to",
                                               evidence="Steve reports to Kenneth")]),
        ]
        claims, conflicts = deduplicate_claims(
            extractions, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )

        assert len(claims) == 1
        assert claims[0].mention_count == 2
        assert len(claims[0].evidence) == 2
        assert claims[0].claim_type == "reports_to"
        assert claims[0].subject_name == "Steven Kean"
        assert claims[0].object_name == "Kenneth Lay"

    def test_different_facts_stay_separate(self):
        """Different subject-object pairs remain separate claims."""
        extractions = [
            make_extraction("msg1", [make_rel("Steven Kean", "Ken Lay", "reports_to")]),
            make_extraction("msg2", [make_rel("Alice Smith", "Bob Jones", "works_with")]),
        ]
        claims, _ = deduplicate_claims(
            extractions, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )
        assert len(claims) == 2

    def test_confidence_takes_max(self):
        """Claim confidence = max across all evidence items."""
        extractions = [
            make_extraction("msg1", [make_rel("Steven Kean", "Ken Lay",
                                               confidence=0.7)]),
            make_extraction("msg2", [make_rel("Steve Kean", "Kenneth Lay",
                                               confidence=0.95)]),
        ]
        claims, _ = deduplicate_claims(
            extractions, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )
        assert claims[0].confidence == 0.95

    def test_valid_from_is_earliest_date(self):
        """valid_from = date of the earliest supporting email."""
        extractions = [
            make_extraction("msg2", [make_rel("Steven Kean", "Ken Lay")]),
            make_extraction("msg1", [make_rel("Steve Kean", "Kenneth Lay")]),
        ]
        claims, _ = deduplicate_claims(
            extractions, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )
        assert claims[0].valid_from == "2001-01-15"  # msg1 date

    def test_valid_to_is_null(self):
        """valid_to starts as null — Day 19 may close it."""
        extractions = [
            make_extraction("msg1", [make_rel("Steven Kean", "Ken Lay")]),
        ]
        claims, _ = deduplicate_claims(
            extractions, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )
        assert claims[0].valid_to is None


# ---------------------------------------------------------------------------
# Symmetric relationship handling
# ---------------------------------------------------------------------------

class TestSymmetricRelationships:
    def test_works_with_both_directions_merge(self):
        """'A works_with B' and 'B works_with A' are the same fact."""
        extractions = [
            make_extraction("msg1", [make_rel("Alice Smith", "Bob Jones",
                                               "works_with", evidence="Alice and Bob work together")]),
            make_extraction("msg2", [make_rel("Bob Jones", "Alice Smith",
                                               "works_with", evidence="Bob collaborates with Alice")]),
        ]
        claims, _ = deduplicate_claims(
            extractions, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )

        works_with = [c for c in claims if c.claim_type == "works_with"]
        assert len(works_with) == 1
        assert works_with[0].mention_count == 2

    def test_reports_to_both_directions_stay_separate(self):
        """'A reports_to B' and 'B reports_to A' are DIFFERENT facts."""
        extractions = [
            make_extraction("msg1", [make_rel("Alice Smith", "Bob Jones", "reports_to")]),
            make_extraction("msg2", [make_rel("Bob Jones", "Alice Smith", "reports_to")]),
        ]
        claims, _ = deduplicate_claims(
            extractions, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )

        reports_to = [c for c in claims if c.claim_type == "reports_to"]
        assert len(reports_to) == 2


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

class TestConflictDetection:
    def test_same_subject_type_different_object_is_conflict(self):
        """Kean reports_to Lay AND Kean reports_to Skilling → conflict."""
        extractions = [
            make_extraction("msg1", [make_rel("Steven Kean", "Ken Lay", "reports_to")]),
            make_extraction("msg3", [make_rel("Steven Kean", "Jeff Skilling", "reports_to")]),
        ]
        claims, conflicts = deduplicate_claims(
            extractions, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )

        assert len(claims) == 2
        assert len(conflicts) == 1
        assert conflicts[0].claim_type == "reports_to"
        assert conflicts[0].subject_name == "Steven Kean"
        assert len(conflicts[0].claims) == 2

    def test_symmetric_multiple_objects_no_conflict(self):
        """Alice works_with Bob AND Alice works_with Kean → NOT a conflict."""
        extractions = [
            make_extraction("msg1", [make_rel("Alice Smith", "Bob Jones", "works_with")]),
            make_extraction("msg2", [make_rel("Alice Smith", "Steven Kean", "works_with")]),
        ]
        _, conflicts = deduplicate_claims(
            extractions, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )
        assert len(conflicts) == 0

    def test_no_conflict_when_same_object(self):
        """Same subject + type + object = duplicate, not conflict."""
        extractions = [
            make_extraction("msg1", [make_rel("Steven Kean", "Ken Lay", "reports_to")]),
            make_extraction("msg2", [make_rel("Steve Kean", "Kenneth Lay", "reports_to")]),
        ]
        _, conflicts = deduplicate_claims(
            extractions, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )
        assert len(conflicts) == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_skips_non_approved(self):
        extractions = [
            make_extraction("msg1", [make_rel("Steven Kean", "Ken Lay",
                                               status="review")]),
        ]
        claims, _ = deduplicate_claims(
            extractions, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )
        assert len(claims) == 0

    def test_skips_duplicate_emails(self):
        extractions = [
            make_extraction("msg1", [make_rel("Steven Kean", "Ken Lay")]),
            make_extraction("dup1", [make_rel("Steven Kean", "Ken Lay")]),
        ]
        claims, _ = deduplicate_claims(
            extractions, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
            duplicate_ids={"dup1"},
        )
        assert len(claims) == 1
        assert claims[0].mention_count == 1

    def test_unresolved_names_get_fallback_id(self):
        extractions = [
            make_extraction("msg1", [make_rel("Unknown Person", "Ken Lay")]),
        ]
        claims, _ = deduplicate_claims(
            extractions, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )
        assert len(claims) == 1
        assert ":unresolved" in claims[0].subject_id

    def test_empty_extractions(self):
        claims, conflicts = deduplicate_claims(
            [], TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )
        assert len(claims) == 0
        assert len(conflicts) == 0

    def test_null_date_handled(self):
        extractions = [
            make_extraction("msg4", [make_rel("Steven Kean", "Ken Lay")]),
        ]
        claims, _ = deduplicate_claims(
            extractions, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )
        assert claims[0].valid_from is None

    def test_claim_id_deterministic(self):
        """Same fact from different runs produces the same claim_id."""
        extractions1 = [make_extraction("msg1", [make_rel("Steven Kean", "Ken Lay")])]
        extractions2 = [make_extraction("msg2", [make_rel("Steve Kean", "Kenneth Lay")])]

        claims1, _ = deduplicate_claims(
            extractions1, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )
        claims2, _ = deduplicate_claims(
            extractions2, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )
        # Same fact (same resolved IDs + same type) → same claim_id
        assert claims1[0].claim_id == claims2[0].claim_id

    def test_description_format(self):
        extractions = [make_extraction("msg1", [make_rel("Steven Kean", "Ken Lay")])]
        claims, _ = deduplicate_claims(
            extractions, TEST_DATES, TEST_RESOLUTION_MAP, TEST_ENTITIES,
        )
        assert claims[0].description == "Steven Kean reports_to Kenneth Lay"