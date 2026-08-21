"""
Unit tests for artifact deduplication.

Tests exact-hash dedup, near-duplicate detection, grouping logic,
primary selection, and the combined pipeline.

Near-duplicate tests use small synthetic examples — they do NOT load
the full sentence-transformer model (that happens only in integration tests
and the batch runner). Exact dedup tests are pure and fast.
"""

import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from src.deduplication.artifact_dedup import (
    normalize_for_hash,
    find_exact_duplicates,
    find_near_duplicates,
    run_artifact_dedup,
    DuplicateGroup,
    ArtifactDedupResult,
    _select_primary,
)


# ---------------------------------------------------------------------------
# normalize_for_hash
# ---------------------------------------------------------------------------

class TestNormalizeForHash:
    def test_collapses_whitespace(self):
        assert normalize_for_hash("hello   world") == "hello world"

    def test_collapses_newlines(self):
        assert normalize_for_hash("hello\n\nworld") == "hello world"

    def test_lowercases(self):
        assert normalize_for_hash("Hello World") == "hello world"

    def test_strips_leading_trailing(self):
        assert normalize_for_hash("  hello  ") == "hello"

    def test_empty_string(self):
        assert normalize_for_hash("") == ""

    def test_hard_wrapped_equivalence(self):
        """Two bodies that differ only in line wrapping produce the same hash."""
        body_76 = "This is a long email that has been\nhard-wrapped at 76 characters"
        body_80 = "This is a long email that has been hard-wrapped at 76\ncharacters"
        assert normalize_for_hash(body_76) == normalize_for_hash(body_80)

    def test_tabs_and_mixed_whitespace(self):
        assert normalize_for_hash("hello\t\t  \n  world") == "hello world"


# ---------------------------------------------------------------------------
# find_exact_duplicates
# ---------------------------------------------------------------------------

class TestFindExactDuplicates:
    def test_no_duplicates(self):
        emails = [
            {"message_id": "a", "body": "Hello from Alice"},
            {"message_id": "b", "body": "Hello from Bob"},
        ]
        groups = find_exact_duplicates(emails)
        assert groups == []

    def test_exact_match(self):
        emails = [
            {"message_id": "a", "body": "Same content here", "date": "2001-01-01"},
            {"message_id": "b", "body": "Same content here", "date": "2001-01-02"},
        ]
        groups = find_exact_duplicates(emails)
        assert len(groups) == 1
        assert groups[0].primary_id == "a"  # earlier date
        assert groups[0].duplicate_ids == ["b"]
        assert groups[0].method == "exact_hash"
        assert groups[0].similarity == 1.0

    def test_whitespace_normalized_match(self):
        """Bodies differing only in whitespace are exact duplicates."""
        emails = [
            {"message_id": "a", "body": "Hello  world", "date": "2001-01-01"},
            {"message_id": "b", "body": "Hello\nworld", "date": "2001-01-02"},
        ]
        groups = find_exact_duplicates(emails)
        assert len(groups) == 1

    def test_case_insensitive_match(self):
        emails = [
            {"message_id": "a", "body": "Hello World", "date": "2001-01-01"},
            {"message_id": "b", "body": "hello world", "date": "2001-01-02"},
        ]
        groups = find_exact_duplicates(emails)
        assert len(groups) == 1

    def test_three_way_duplicate(self):
        emails = [
            {"message_id": "a", "body": "same", "date": "2001-03-01"},
            {"message_id": "b", "body": "same", "date": "2001-01-01"},
            {"message_id": "c", "body": "same", "date": "2001-02-01"},
        ]
        groups = find_exact_duplicates(emails)
        assert len(groups) == 1
        assert groups[0].primary_id == "b"  # earliest date
        assert set(groups[0].duplicate_ids) == {"a", "c"}

    def test_multiple_groups(self):
        emails = [
            {"message_id": "a1", "body": "group one"},
            {"message_id": "a2", "body": "group one"},
            {"message_id": "b1", "body": "group two"},
            {"message_id": "b2", "body": "group two"},
            {"message_id": "c", "body": "unique"},
        ]
        groups = find_exact_duplicates(emails)
        assert len(groups) == 2

    def test_empty_body_treated_as_single_group(self):
        """Multiple emails with empty bodies are exact duplicates of each other."""
        emails = [
            {"message_id": "a", "body": ""},
            {"message_id": "b", "body": ""},
            {"message_id": "c", "body": "actual content"},
        ]
        groups = find_exact_duplicates(emails)
        assert len(groups) == 1
        assert set([groups[0].primary_id] + groups[0].duplicate_ids) == {"a", "b"}

    def test_none_body_handled(self):
        emails = [
            {"message_id": "a", "body": None},
            {"message_id": "b", "body": "real content"},
        ]
        groups = find_exact_duplicates(emails)
        assert len(groups) == 0  # None → "" only one email with that hash

    def test_primary_selection_prefers_earliest_date(self):
        emails = [
            {"message_id": "late", "body": "same", "date": "2001-12-01"},
            {"message_id": "early", "body": "same", "date": "2001-01-01"},
        ]
        groups = find_exact_duplicates(emails)
        assert groups[0].primary_id == "early"

    def test_primary_selection_null_date_sorts_last(self):
        emails = [
            {"message_id": "no_date", "body": "same", "date": None},
            {"message_id": "has_date", "body": "same", "date": "2001-01-01"},
        ]
        groups = find_exact_duplicates(emails)
        assert groups[0].primary_id == "has_date"

    def test_empty_input(self):
        assert find_exact_duplicates([]) == []

    def test_single_email(self):
        assert find_exact_duplicates([{"message_id": "a", "body": "solo"}]) == []


# ---------------------------------------------------------------------------
# _select_primary
# ---------------------------------------------------------------------------

class TestSelectPrimary:
    def test_earliest_date_wins(self):
        entries = [
            {"message_id": "late", "date": "2001-06-01", "body": "x"},
            {"message_id": "early", "date": "2001-01-01", "body": "x"},
        ]
        primary, dups = _select_primary(entries)
        assert primary["message_id"] == "early"
        assert len(dups) == 1

    def test_longest_body_breaks_date_tie(self):
        entries = [
            {"message_id": "short", "date": "2001-01-01", "body": "hi"},
            {"message_id": "long", "date": "2001-01-01", "body": "hi there friend"},
        ]
        primary, dups = _select_primary(entries)
        assert primary["message_id"] == "long"

    def test_message_id_breaks_final_tie(self):
        entries = [
            {"message_id": "b", "date": "2001-01-01", "body": "same"},
            {"message_id": "a", "date": "2001-01-01", "body": "same"},
        ]
        primary, dups = _select_primary(entries)
        assert primary["message_id"] == "a"


# ---------------------------------------------------------------------------
# DuplicateGroup and ArtifactDedupResult
# ---------------------------------------------------------------------------

class TestDataStructures:
    def test_duplicate_group_to_dict(self):
        g = DuplicateGroup("a", ["b", "c"], "exact_hash", 1.0, "test")
        d = g.to_dict()
        assert d["primary_id"] == "a"
        assert d["duplicate_ids"] == ["b", "c"]

    def test_result_duplicate_ids(self):
        result = ArtifactDedupResult(
            exact_groups=[DuplicateGroup("a", ["b"], "exact_hash", 1.0, "r")],
            near_groups=[DuplicateGroup("c", ["d", "e"], "near_duplicate", 0.96, "r")],
        )
        assert result.duplicate_ids == {"b", "d", "e"}
        assert result.primary_ids == {"a", "c"}

    def test_result_summary(self):
        result = ArtifactDedupResult(
            exact_groups=[DuplicateGroup("a", ["b"], "exact_hash", 1.0, "r")],
            near_groups=[],
        )
        s = result.summary()
        assert s["exact_duplicate_groups"] == 1
        assert s["near_duplicate_groups"] == 0
        assert s["total_duplicates_to_skip"] == 1

    def test_empty_result(self):
        result = ArtifactDedupResult()
        assert result.duplicate_ids == set()
        assert result.summary()["total_groups"] == 0


# ---------------------------------------------------------------------------
# find_near_duplicates (with mocked model)
# ---------------------------------------------------------------------------

class TestFindNearDuplicates:
    """Tests near-duplicate detection by mocking the sentence-transformer.

    We provide pre-computed embeddings so tests run in milliseconds,
    not the 30+ seconds it takes to load the real model.
    """

    def _make_mock_model(self, embeddings: np.ndarray):
        """Create a mock SentenceTransformer that returns given embeddings."""
        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        return mock_model

    @patch("src.deduplication.artifact_dedup.SentenceTransformer")
    def test_identical_embeddings_detected(self, MockST):
        """Two emails with identical embeddings are near-duplicates."""
        emb = np.array([
            [1.0, 0.0, 0.0],  # email 0
            [1.0, 0.0, 0.0],  # email 1 — identical
            [0.0, 1.0, 0.0],  # email 2 — different
        ], dtype=np.float32)
        # normalize
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        emb = emb / norms

        MockST.return_value.encode.return_value = emb

        emails = [
            {"message_id": "a", "body": "same", "date": "2001-01-01"},
            {"message_id": "b", "body": "same too", "date": "2001-01-02"},
            {"message_id": "c", "body": "different", "date": "2001-01-03"},
        ]
        groups = find_near_duplicates(emails, threshold=0.95)
        assert len(groups) == 1
        assert groups[0].primary_id == "a"
        assert groups[0].duplicate_ids == ["b"]

    @patch("src.deduplication.artifact_dedup.SentenceTransformer")
    def test_below_threshold_not_grouped(self, MockST):
        """Emails with similarity below threshold are NOT grouped."""
        emb = np.array([
            [1.0, 0.0, 0.0],
            [0.7, 0.7, 0.0],  # cosine ~ 0.707, below 0.95
        ], dtype=np.float32)
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        emb = emb / norms

        MockST.return_value.encode.return_value = emb

        emails = [
            {"message_id": "a", "body": "x"},
            {"message_id": "b", "body": "y"},
        ]
        groups = find_near_duplicates(emails, threshold=0.95)
        assert len(groups) == 0

    @patch("src.deduplication.artifact_dedup.SentenceTransformer")
    def test_transitive_grouping(self, MockST):
        """If A~B and B~C, all three form one group (transitivity via Union-Find)."""
        # A and B similar, B and C similar, A and C less similar
        # but transitively they should all group
        emb = np.array([
            [1.0, 0.0, 0.0],    # A
            [0.98, 0.2, 0.0],   # B — close to A
            [0.95, 0.31, 0.0],  # C — close to B
        ], dtype=np.float32)
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        emb = emb / norms

        MockST.return_value.encode.return_value = emb

        emails = [
            {"message_id": "a", "body": "x", "date": "2001-01-01"},
            {"message_id": "b", "body": "x", "date": "2001-01-02"},
            {"message_id": "c", "body": "x", "date": "2001-01-03"},
        ]
        groups = find_near_duplicates(emails, threshold=0.95)
        assert len(groups) == 1
        assert groups[0].primary_id == "a"
        assert set(groups[0].duplicate_ids) == {"b", "c"}

    @patch("src.deduplication.artifact_dedup.SentenceTransformer")
    def test_empty_input(self, MockST):
        groups = find_near_duplicates([], threshold=0.95)
        assert groups == []

    @patch("src.deduplication.artifact_dedup.SentenceTransformer")
    def test_single_email(self, MockST):
        groups = find_near_duplicates(
            [{"message_id": "a", "body": "solo"}],
            threshold=0.95,
        )
        assert groups == []

    @patch("src.deduplication.artifact_dedup.SentenceTransformer")
    def test_uses_original_content_when_available(self, MockST):
        """Prefers 'original_content' over 'body' for embedding."""
        emb = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        MockST.return_value.encode.return_value = emb / norms

        emails = [
            {"message_id": "a", "body": "full body with noise",
             "original_content": "just the content"},
            {"message_id": "b", "body": "other"},
        ]
        find_near_duplicates(emails, threshold=0.95)

        # Check that encode was called with original_content, not body
        call_args = MockST.return_value.encode.call_args
        texts = call_args[0][0]
        assert texts[0] == "just the content"


# ---------------------------------------------------------------------------
# run_artifact_dedup (combined pipeline)
# ---------------------------------------------------------------------------

class TestRunArtifactDedup:
    def test_exact_only_mode(self):
        emails = [
            {"message_id": "a", "body": "same", "date": "2001-01-01"},
            {"message_id": "b", "body": "same", "date": "2001-01-02"},
        ]
        result = run_artifact_dedup(emails, skip_near_duplicates=True)
        assert len(result.exact_groups) == 1
        assert len(result.near_groups) == 0
        assert result.duplicate_ids == {"b"}

    def test_no_duplicates(self):
        emails = [
            {"message_id": "a", "body": "alpha"},
            {"message_id": "b", "body": "beta"},
        ]
        result = run_artifact_dedup(emails, skip_near_duplicates=True)
        assert result.duplicate_ids == set()

    @patch("src.deduplication.artifact_dedup.find_near_duplicates")
    def test_exact_dupes_excluded_from_near_dup_search(self, mock_near):
        """Emails already flagged as exact duplicates aren't passed to near-dup detection."""
        mock_near.return_value = []
        emails = [
            {"message_id": "a", "body": "same", "date": "2001-01-01"},
            {"message_id": "b", "body": "same", "date": "2001-01-02"},
            {"message_id": "c", "body": "unique"},
        ]
        run_artifact_dedup(emails)

        # near-dup should receive only "a" and "c" (not "b", which is an exact dup)
        remaining = mock_near.call_args[0][0]
        remaining_ids = {e["message_id"] for e in remaining}
        assert "b" not in remaining_ids
        assert "a" in remaining_ids
        assert "c" in remaining_ids