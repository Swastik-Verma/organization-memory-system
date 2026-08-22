"""
Unit tests for fuzzy entity matching (Day 17).

Tests nickname expansion, middle initial stripping, candidate finding,
merge application, and undo capability.
"""

import pytest
from src.deduplication.fuzzy_matcher import (
    get_name_variants,
    strip_middle_initials,
    get_email_domain,
    get_last_name,
    FuzzyMatcher,
    MergeCandidate,
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestGetNameVariants:
    def test_nickname_to_formal(self):
        variants = get_name_variants("Ken Lay")
        assert "kenneth lay" in variants
        assert "ken lay" in variants

    def test_formal_to_nickname(self):
        variants = get_name_variants("Kenneth Lay")
        assert "ken lay" in variants
        assert "kenny lay" in variants
        assert "kenneth lay" in variants

    def test_no_nickname(self):
        variants = get_name_variants("Zelda Quincy")
        assert variants == {"zelda quincy"}

    def test_multiple_parts_expanded(self):
        variants = get_name_variants("Mike Steve")
        # "mike" → "michael", "steve" → "steven"
        assert "michael steve" in variants
        assert "mike steven" in variants

    def test_case_insensitive(self):
        variants = get_name_variants("KEN LAY")
        assert "kenneth lay" in variants


class TestStripMiddleInitials:
    def test_single_initial(self):
        assert strip_middle_initials("Steven J Kean") == "Steven Kean"

    def test_initial_with_period(self):
        assert strip_middle_initials("Steven J. Kean") == "Steven Kean"

    def test_no_initials(self):
        assert strip_middle_initials("Steven Kean") == "Steven Kean"

    def test_multiple_initials(self):
        assert strip_middle_initials("J. K. Rowling") == "Rowling"

    def test_all_initials_fallback(self):
        """If all parts are initials, return original (no useful result from stripping)."""
        assert strip_middle_initials("J. K.") == "J. K."

    def test_single_word(self):
        assert strip_middle_initials("Vince") == "Vince"


class TestGetEmailDomain:
    def test_normal_email(self):
        assert get_email_domain("ken@enron.com") == "enron.com"

    def test_subdomain(self):
        assert get_email_domain("vince@ect.enron.com") == "ect.enron.com"

    def test_none(self):
        assert get_email_domain(None) is None

    def test_no_at(self):
        assert get_email_domain("invalid") is None


class TestGetLastName:
    def test_normal(self):
        assert get_last_name("Steven Kean") == "kean"

    def test_single_name(self):
        assert get_last_name("Vince") == "vince"

    def test_empty(self):
        assert get_last_name("") == ""


# ---------------------------------------------------------------------------
# Helper: build entity dicts for testing
# ---------------------------------------------------------------------------

def make_entity(
    canonical_id: str,
    canonical_name: str,
    entity_type: str = "person",
    aliases: list[str] | None = None,
    emails: list[str] | None = None,
    mention_count: int = 100,
) -> dict:
    return {
        "canonical_id": canonical_id,
        "canonical_name": canonical_name,
        "entity_type": entity_type,
        "aliases": aliases or [canonical_name],
        "emails": emails or [],
        "mention_count": mention_count,
        "org_type": None,
    }


# ---------------------------------------------------------------------------
# FuzzyMatcher — candidate finding
# ---------------------------------------------------------------------------

class TestFindCandidates:
    def test_middle_initial_found(self):
        entities = {
            "p1": make_entity("p1", "Steven Kean", emails=["sk@enron.com"]),
            "p2": make_entity("p2", "Steven J Kean", emails=["sk2@enron.com"]),
        }
        matcher = FuzzyMatcher(entities, {})
        candidates = matcher.find_candidates()
        assert len(candidates) >= 1
        pair_found = any(
            (c.source_id in ("p1", "p2") and c.target_id in ("p1", "p2"))
            for c in candidates
        )
        assert pair_found

    def test_nickname_found(self):
        entities = {
            "p1": make_entity("p1", "Kenneth Lay"),
            "p2": make_entity("p2", "Ken Lay"),
        }
        matcher = FuzzyMatcher(entities, {})
        candidates = matcher.find_candidates()

        nickname = [c for c in candidates if c.strategy == "nickname"]
        assert len(nickname) >= 1

    def test_same_domain_found(self):
        """Same name + same email domain → candidate."""
        entities = {
            "p1": make_entity("p1", "Kenneth Lay", emails=["klay@enron.com"],
                              mention_count=200),
            "p2": make_entity("p2", "Kenneth Lay", emails=["kenneth.lay@enron.com"],
                              mention_count=1000),
        }
        matcher = FuzzyMatcher(entities, {})
        candidates = matcher.find_candidates()

        same_domain = [c for c in candidates if c.strategy == "same_domain"]
        assert len(same_domain) >= 1

    def test_fuzzy_typo_found(self):
        """Typo in first name caught by fuzzy matching within same last-name block."""
        entities = {
            "p1": make_entity("p1", "Jeffery Smith"),
            "p2": make_entity("p2", "Jeffrey Smith"),  # typo in first name
        }
        matcher = FuzzyMatcher(entities, {})
        candidates = matcher.find_candidates()
        assert len(candidates) >= 1

    def test_completely_different_not_found(self):
        """Very different names should not match."""
        entities = {
            "p1": make_entity("p1", "Alice Smith"),
            "p2": make_entity("p2", "Bob Johnson"),
        }
        matcher = FuzzyMatcher(entities, {})
        candidates = matcher.find_candidates()
        assert len(candidates) == 0

    def test_org_fuzzy_matching(self):
        """Organizations should also be fuzzy matched."""
        entities = {
            "o1": make_entity("o1", "Pacific Gas Electric", entity_type="organization"),
            "o2": make_entity("o2", "Pacific Gas & Electric", entity_type="organization"),
        }
        matcher = FuzzyMatcher(entities, {})
        candidates = matcher.find_candidates()
        assert len(candidates) >= 1


# ---------------------------------------------------------------------------
# FuzzyMatcher — merge application
# ---------------------------------------------------------------------------

class TestApplyMerges:
    def test_merge_transfers_aliases(self):
        entities = {
            "p1": make_entity("p1", "Ken Lay", aliases=["Ken Lay"],
                              emails=["klay@enron.com"], mention_count=100),
            "p2": make_entity("p2", "Kenneth Lay", aliases=["Kenneth Lay"],
                              emails=["kenneth.lay@enron.com"], mention_count=500),
        }
        res_map = {"Ken Lay": "p1", "Kenneth Lay": "p2"}

        matcher = FuzzyMatcher(entities, res_map)
        candidates = matcher.find_candidates()
        matcher.apply_merges(candidates, auto_threshold=0.80)

        # p1 should be absorbed into p2
        assert "p1" not in matcher.entities
        assert "p2" in matcher.entities
        p2 = matcher.entities["p2"]
        assert "Ken Lay" in p2["aliases"]
        assert "Kenneth Lay" in p2["aliases"]
        assert "klay@enron.com" in p2["emails"]
        assert "kenneth.lay@enron.com" in p2["emails"]
        assert p2["mention_count"] == 600

    def test_merge_updates_resolution_map(self):
        entities = {
            "p1": make_entity("p1", "Ken Lay", mention_count=100),
            "p2": make_entity("p2", "Kenneth Lay", mention_count=500),
        }
        res_map = {"Ken Lay": "p1", "Kenneth Lay": "p2"}

        matcher = FuzzyMatcher(entities, res_map)
        candidates = matcher.find_candidates()
        matcher.apply_merges(candidates, auto_threshold=0.80)

        # Both names should now point to p2
        assert matcher.resolution_map["Ken Lay"] == "p2"
        assert matcher.resolution_map["Kenneth Lay"] == "p2"

    def test_below_threshold_not_merged(self):
        entities = {
            "p1": make_entity("p1", "Alice Smith"),
            "p2": make_entity("p2", "Alice Smithson"),
        }
        matcher = FuzzyMatcher(entities, {})
        candidates = matcher.find_candidates()
        merged = matcher.apply_merges(candidates, auto_threshold=0.99)
        assert merged == 0
        assert len(matcher.entities) == 2


# ---------------------------------------------------------------------------
# FuzzyMatcher — undo
# ---------------------------------------------------------------------------

class TestUndo:
    def test_undo_restores_both_entities(self):
        entities = {
            "p1": make_entity("p1", "Ken Lay", aliases=["Ken Lay"],
                              emails=["klay@enron.com"], mention_count=100),
            "p2": make_entity("p2", "Kenneth Lay", aliases=["Kenneth Lay"],
                              emails=["kenneth.lay@enron.com"], mention_count=500),
        }
        res_map = {"Ken Lay": "p1", "Kenneth Lay": "p2"}

        matcher = FuzzyMatcher(entities, res_map)
        candidates = matcher.find_candidates()
        matcher.apply_merges(candidates, auto_threshold=0.80)

        # Verify merged
        assert "p1" not in matcher.entities
        assert len(matcher.merge_operations) == 1

        # Undo
        merge_id = matcher.merge_operations[0].merge_id
        success = matcher.undo_merge(merge_id)
        assert success

        # Both entities restored
        assert "p1" in matcher.entities
        assert "p2" in matcher.entities
        assert matcher.entities["p1"]["mention_count"] == 100
        assert matcher.entities["p2"]["mention_count"] == 500
        assert "Ken Lay" not in matcher.entities["p2"]["aliases"]

    def test_undo_restores_resolution_map(self):
        entities = {
            "p1": make_entity("p1", "Ken Lay", aliases=["Ken Lay"],
                              mention_count=100),
            "p2": make_entity("p2", "Kenneth Lay", aliases=["Kenneth Lay"],
                              mention_count=500),
        }
        res_map = {"Ken Lay": "p1", "Kenneth Lay": "p2"}

        matcher = FuzzyMatcher(entities, res_map)
        candidates = matcher.find_candidates()
        matcher.apply_merges(candidates, auto_threshold=0.80)

        # Both point to p2 after merge
        assert matcher.resolution_map["Ken Lay"] == "p2"

        # Undo
        merge_id = matcher.merge_operations[0].merge_id
        matcher.undo_merge(merge_id)

        # Restored: Ken Lay points back to p1
        assert matcher.resolution_map["Ken Lay"] == "p1"
        assert matcher.resolution_map["Kenneth Lay"] == "p2"

    def test_undo_nonexistent_id(self):
        matcher = FuzzyMatcher({}, {})
        assert matcher.undo_merge("nonexistent") is False

    def test_undo_already_undone(self):
        entities = {
            "p1": make_entity("p1", "Ken Lay", mention_count=100),
            "p2": make_entity("p2", "Kenneth Lay", mention_count=500),
        }
        matcher = FuzzyMatcher(entities, {"Ken Lay": "p1", "Kenneth Lay": "p2"})
        candidates = matcher.find_candidates()
        matcher.apply_merges(candidates, auto_threshold=0.80)

        merge_id = matcher.merge_operations[0].merge_id
        matcher.undo_merge(merge_id)
        assert matcher.undo_merge(merge_id) is False  # already undone

    def test_merge_operation_status(self):
        entities = {
            "p1": make_entity("p1", "Ken Lay", mention_count=100),
            "p2": make_entity("p2", "Kenneth Lay", mention_count=500),
        }
        matcher = FuzzyMatcher(entities, {"Ken Lay": "p1", "Kenneth Lay": "p2"})
        candidates = matcher.find_candidates()
        matcher.apply_merges(candidates, auto_threshold=0.80)

        assert matcher.merge_operations[0].status == "active"
        matcher.undo_merge(matcher.merge_operations[0].merge_id)
        assert matcher.merge_operations[0].status == "undone"