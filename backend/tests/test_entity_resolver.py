"""
Unit tests for entity resolution — exact matching phase.

Tests name normalization, email-based resolution, name-based resolution,
canonical name selection, shared email detection, and the merge audit log.
"""

import pytest
from src.deduplication.entity_resolver import (
    normalize_person_name,
    normalize_org_name,
    EntityResolver,
    CanonicalEntity,
    MergeRecord,
    _choose_canonical_name,
)


# ---------------------------------------------------------------------------
# Person name normalization
# ---------------------------------------------------------------------------

class TestNormalizePersonName:
    def test_basic_lowercase(self):
        assert normalize_person_name("Steven Kean") == "kean steven"

    def test_already_lowercase(self):
        assert normalize_person_name("steven kean") == "kean steven"

    def test_comma_reordering(self):
        """'Last, First' should match 'First Last'."""
        assert normalize_person_name("Kean, Steven") == "kean steven"

    def test_strips_mr(self):
        assert normalize_person_name("Mr. Steven Kean") == "kean steven"

    def test_strips_dr(self):
        assert normalize_person_name("Dr. Vince Kaminski") == "kaminski vince"

    def test_strips_jr(self):
        assert normalize_person_name("Kenneth Lay Jr.") == "kenneth lay"

    def test_period_in_name(self):
        """Periods become spaces, then parts sort."""
        assert normalize_person_name("steven.kean") == "kean steven"

    def test_middle_initial_preserved(self):
        """Middle initials produce a DIFFERENT normalized form — this is exact matching."""
        assert normalize_person_name("Steven J Kean") == "j kean steven"
        assert normalize_person_name("Steven Kean") == "kean steven"
        # These are different — Day 17 fuzzy matching catches this
        assert normalize_person_name("Steven J Kean") != normalize_person_name("Steven Kean")

    def test_all_caps(self):
        assert normalize_person_name("STEVEN KEAN") == "kean steven"

    def test_extra_whitespace(self):
        assert normalize_person_name("  Steven   Kean  ") == "kean steven"

    def test_empty_string(self):
        assert normalize_person_name("") == ""

    def test_none_like(self):
        """Edge case: name that becomes empty after stripping titles."""
        assert normalize_person_name("Mr.") == ""

    def test_sorting_is_alphabetical(self):
        assert normalize_person_name("Zelda Alice") == "alice zelda"


# ---------------------------------------------------------------------------
# Organization name normalization
# ---------------------------------------------------------------------------

class TestNormalizeOrgName:
    def test_strips_corp(self):
        assert normalize_org_name("Enron Corp.") == "enron"

    def test_strips_corporation(self):
        assert normalize_org_name("Enron Corporation") == "enron"

    def test_strips_inc(self):
        assert normalize_org_name("Apple Inc.") == "apple"

    def test_strips_llc(self):
        assert normalize_org_name("My Company LLC") == "my company"

    def test_preserves_word_order(self):
        """Unlike person names, org name word order matters."""
        assert normalize_org_name("Enron North America") == "enron north america"

    def test_does_not_sort(self):
        result = normalize_org_name("North America Enron")
        assert result == "north america enron"

    def test_strips_only_trailing_suffixes(self):
        """'International Paper' should keep 'International'."""
        assert normalize_org_name("International Paper") == "international paper"

    def test_strips_multiple_trailing(self):
        assert normalize_org_name("Acme Holdings Corp.") == "acme holdings"

    def test_empty_string(self):
        assert normalize_org_name("") == ""

    def test_case_insensitive(self):
        assert normalize_org_name("ENRON CORP") == "enron"

    def test_matching_variants(self):
        """Two common ways to write the same org should normalize identically."""
        assert normalize_org_name("Enron Corp.") == normalize_org_name("Enron Corporation")


# ---------------------------------------------------------------------------
# Canonical name selection
# ---------------------------------------------------------------------------

class TestChooseCanonicalName:
    def test_most_frequent_wins(self):
        aliases = {"Steven Kean", "Steven J Kean", "steve kean"}
        counts = {"Steven Kean": 786, "Steven J Kean": 266, "steve kean": 12}
        assert _choose_canonical_name(aliases, counts) == "Steven Kean"

    def test_longest_breaks_tie(self):
        aliases = {"Steve K", "Steve Kean"}
        counts = {"Steve K": 100, "Steve Kean": 100}
        assert _choose_canonical_name(aliases, counts) == "Steve Kean"

    def test_single_alias(self):
        aliases = {"John Smith"}
        counts = {"John Smith": 50}
        assert _choose_canonical_name(aliases, counts) == "John Smith"


# ---------------------------------------------------------------------------
# EntityResolver — Person resolution
# ---------------------------------------------------------------------------

class TestResolvePersonEmail:
    def test_same_email_merges(self):
        """Two different names with the same email resolve to one entity."""
        resolver = EntityResolver()
        id1 = resolver.resolve_person("Steven Kean", "steven.kean@enron.com", 786)
        id2 = resolver.resolve_person("Steven J Kean", "steven.kean@enron.com", 266)
        assert id1 == id2

    def test_merged_entity_has_both_aliases(self):
        resolver = EntityResolver()
        resolver.resolve_person("Steven Kean", "steven.kean@enron.com", 786)
        resolver.resolve_person("Steven J Kean", "steven.kean@enron.com", 266)
        resolver.finalize()

        entities = resolver.get_canonical_entities()
        # Find the entity
        entity = [e for e in entities.values() if "Steven Kean" in e["aliases"]][0]
        assert "Steven Kean" in entity["aliases"]
        assert "Steven J Kean" in entity["aliases"]
        assert entity["mention_count"] == 786 + 266

    def test_different_emails_stay_separate(self):
        resolver = EntityResolver()
        id1 = resolver.resolve_person("Alice Smith", "alice@enron.com")
        id2 = resolver.resolve_person("Bob Jones", "bob@enron.com")
        assert id1 != id2

    def test_email_none_falls_to_name_matching(self):
        """Without email, two identical normalized names merge."""
        resolver = EntityResolver()
        id1 = resolver.resolve_person("Steven Kean", None, 10)
        id2 = resolver.resolve_person("Kean, Steven", None, 5)  # same normalized
        assert id1 == id2

    def test_email_takes_priority_over_name(self):
        """If email matches entity A but name matches entity B, email wins."""
        resolver = EntityResolver()
        # Create entity via name
        id1 = resolver.resolve_person("Alice Smith", None, 10)
        # Create different entity via different name
        id2 = resolver.resolve_person("Bob Jones", "shared@enron.com", 10)
        # Now "Alice Jones" arrives with Bob's email — should merge with Bob
        id3 = resolver.resolve_person("Alice Jones", "shared@enron.com", 5)
        assert id3 == id2  # email match wins
        assert id3 != id1

    def test_null_email_treated_as_none(self):
        resolver = EntityResolver()
        id1 = resolver.resolve_person("John Smith", "", 1)
        id2 = resolver.resolve_person("John Smith", None, 1)
        assert id1 == id2


class TestResolvePersonName:
    def test_comma_reordering_merges(self):
        resolver = EntityResolver()
        id1 = resolver.resolve_person("Steven Kean")
        id2 = resolver.resolve_person("Kean, Steven")
        assert id1 == id2

    def test_case_insensitive(self):
        resolver = EntityResolver()
        id1 = resolver.resolve_person("Steven Kean")
        id2 = resolver.resolve_person("STEVEN KEAN")
        assert id1 == id2

    def test_title_stripped(self):
        resolver = EntityResolver()
        id1 = resolver.resolve_person("Steven Kean")
        id2 = resolver.resolve_person("Mr. Steven Kean")
        assert id1 == id2

    def test_middle_initial_stays_separate(self):
        """Day 16 exact matching does NOT merge these — Day 17 will."""
        resolver = EntityResolver()
        id1 = resolver.resolve_person("Steven Kean")
        id2 = resolver.resolve_person("Steven J Kean")
        assert id1 != id2  # different normalized forms

    def test_nickname_stays_separate(self):
        """Day 16 exact matching does NOT merge these — Day 17 will."""
        resolver = EntityResolver()
        id1 = resolver.resolve_person("Kenneth Lay")
        id2 = resolver.resolve_person("Ken Lay")
        assert id1 != id2


# ---------------------------------------------------------------------------
# Shared email detection
# ---------------------------------------------------------------------------

class TestSharedEmail:
    def test_shared_email_skipped(self):
        """An email used by >5 different people is treated as shared."""
        resolver = EntityResolver()
        # Six different people all using the same email
        for i in range(6):
            resolver.resolve_person(f"Person{i} Unique{i}", "shared@enron.com")

        stats = resolver.get_stats()
        assert len(stats["shared_email_addresses"]) > 0
        assert "shared@enron.com" in stats["shared_email_addresses"]

    def test_normal_email_not_flagged(self):
        resolver = EntityResolver()
        resolver.resolve_person("Steven Kean", "steven.kean@enron.com")
        resolver.resolve_person("Steven J Kean", "steven.kean@enron.com")
        stats = resolver.get_stats()
        assert len(stats["shared_email_addresses"]) == 0


# ---------------------------------------------------------------------------
# Organization resolution
# ---------------------------------------------------------------------------

class TestResolveOrganization:
    def test_corp_variants_merge(self):
        resolver = EntityResolver()
        id1 = resolver.resolve_organization("Enron Corp.")
        id2 = resolver.resolve_organization("Enron Corporation")
        assert id1 == id2

    def test_different_orgs_stay_separate(self):
        resolver = EntityResolver()
        id1 = resolver.resolve_organization("Enron Corp.")
        id2 = resolver.resolve_organization("Pacific Gas and Electric")
        assert id1 != id2

    def test_case_insensitive(self):
        resolver = EntityResolver()
        id1 = resolver.resolve_organization("Enron")
        id2 = resolver.resolve_organization("ENRON")
        assert id1 == id2

    def test_org_type_preserved(self):
        resolver = EntityResolver()
        resolver.resolve_organization("Enron Corp.", "company")
        resolver.finalize()
        entities = resolver.get_canonical_entities()
        enron = [e for e in entities.values() if "Enron Corp." in e["aliases"]][0]
        assert enron["org_type"] == "company"

    def test_word_order_matters(self):
        """Unlike person names, org word order is significant."""
        resolver = EntityResolver()
        id1 = resolver.resolve_organization("Enron North America")
        id2 = resolver.resolve_organization("North America Enron")
        assert id1 != id2


    def test_same_name_no_email_merges_with_most_mentioned(self):
        """When name matches multiple entities and no email, pick highest count."""
        resolver = EntityResolver()
        resolver.resolve_person("Alice Smith", "alice.smith@enron.com", 500)
        resolver.resolve_person("Alice Smith", "a.smith@enron.com", 50)
        id3 = resolver.resolve_person("Alice Smith", None, 1)

        # Should merge with the 500-mention entity (most mentioned)
        id1 = resolver.resolve_person("Alice Smith", "alice.smith@enron.com")
        assert id3 == id1

    def test_same_name_matching_email_picks_correct_one(self):
        """When name matches multiple but email matches one, pick that one."""
        resolver = EntityResolver()
        id1 = resolver.resolve_person("Alice Smith", "alice.smith@enron.com", 100)
        id2 = resolver.resolve_person("Alice Smith", "a.smith@enron.com", 100)
        id3 = resolver.resolve_person("Alice Smith", "a.smith@enron.com", 1)
        assert id3 == id2  # email match picks the right one
        assert id3 != id1


# ---------------------------------------------------------------------------
# Merge audit log
# ---------------------------------------------------------------------------

class TestMergeLog:
    def test_merge_logged(self):
        resolver = EntityResolver()
        resolver.resolve_person("Steven Kean", "steven.kean@enron.com", 786)
        resolver.resolve_person("Steven J Kean", "steven.kean@enron.com", 266)

        log = resolver.get_merge_log()
        assert len(log) == 1  # first call creates; second call merges
        assert log[0]["merged_name"] == "Steven J Kean"
        assert log[0]["reason"] == "email_match"
        assert log[0]["confidence"] == 1.0

    def test_no_merge_for_same_name_repeat(self):
        """Same name appearing again is not a 'merge' — just a count bump."""
        resolver = EntityResolver()
        resolver.resolve_person("Steven Kean", None, 100)
        resolver.resolve_person("Steven Kean", None, 50)

        log = resolver.get_merge_log()
        assert len(log) == 0  # no new alias added

    def test_org_merge_logged(self):
        resolver = EntityResolver()
        resolver.resolve_organization("Enron Corp.")
        resolver.resolve_organization("Enron Corporation")

        log = resolver.get_merge_log()
        assert len(log) == 1
        assert log[0]["reason"] == "normalized_name_match"


# ---------------------------------------------------------------------------
# Resolution map and finalization
# ---------------------------------------------------------------------------

class TestResolutionMap:
    def test_all_aliases_in_map(self):
        resolver = EntityResolver()
        resolver.resolve_person("Steven Kean", "steven.kean@enron.com")
        resolver.resolve_person("Steven J Kean", "steven.kean@enron.com")

        res_map = resolver.get_resolution_map()
        assert res_map["Steven Kean"] == res_map["Steven J Kean"]

    def test_canonical_name_is_most_frequent(self):
        resolver = EntityResolver()
        resolver.resolve_person("Steven Kean", "steven.kean@enron.com", 786)
        resolver.resolve_person("Steven J Kean", "steven.kean@enron.com", 266)
        resolver.finalize()

        entities = resolver.get_canonical_entities()
        cid = resolver.get_resolution_map()["Steven Kean"]
        assert entities[cid]["canonical_name"] == "Steven Kean"  # more frequent

    def test_stats_counts(self):
        resolver = EntityResolver()
        resolver.resolve_person("Steven Kean", "sk@enron.com", 786)
        resolver.resolve_person("Steven J Kean", "sk@enron.com", 266)
        resolver.resolve_person("Ken Lay", None, 500)
        resolver.resolve_organization("Enron Corp.", "company")
        resolver.resolve_organization("Enron Corporation", "company")

        stats = resolver.get_stats()
        assert stats["total_unique_person_names_input"] == 3
        assert stats["canonical_people"] == 2  # Kean merged, Lay separate
        assert stats["person_names_collapsed"] == 1
        assert stats["total_unique_org_names_input"] == 2
        assert stats["canonical_orgs"] == 1  # both Enron variants merge
        assert stats["org_names_collapsed"] == 1

    def test_empty_resolver(self):
        resolver = EntityResolver()
        assert resolver.get_stats()["canonical_people"] == 0
        assert resolver.get_resolution_map() == {}

    def test_empty_name_skipped(self):
        resolver = EntityResolver()
        result = resolver.resolve_person("", None)
        assert result == ""
        assert resolver.get_stats()["canonical_people"] == 0