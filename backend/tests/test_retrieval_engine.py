"""Tests for the retrieval engine module."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from src.retrieval.retrieval_engine import (
    RetrievalEngine,
    RetrievedClaim,
    ContextPack,
    RetrievalMetadata,
    _format_date,
)
from src.retrieval.query_understanding import (
    QueryPlan,
    QuestionType,
    TimeConstraint,
    TimeConstraintType,
    RetrievalStrategy,
    ResolvedEntity,
)


def _make_engine():
    """Create a RetrievalEngine with mocked dependencies."""
    driver = MagicMock()
    qdrant = MagicMock()
    engine = RetrievalEngine(neo4j_driver=driver, qdrant_index=qdrant)
    return engine, driver, qdrant


def _make_plan(**overrides):
    """Create a minimal QueryPlan for testing."""
    defaults = {
        "raw_query": "test question",
        "question_type": QuestionType.WHO,
        "entities": [],
        "time_constraint": TimeConstraint(TimeConstraintType.NONE),
        "retrieval_strategy": RetrievalStrategy.GRAPH,
        "claim_types": [],
        "needs_clarification": False,
        "clarification_reason": None,
        "semantic_query": None,
    }
    defaults.update(overrides)
    return QueryPlan(**defaults)


class TestMergeResults:
    """Test _merge_results deduplication logic."""

    def test_no_overlap(self):
        engine, _, _ = _make_engine()

        graph = [RetrievedClaim(
            claim_id="c1", claim_type="reports_to",
            subject_id="s1", subject_name="A", object_id="o1",
            object_name="B", confidence=0.9, valid_from=None,
            valid_to=None, status="current", mention_count=5,
            source="graph",
        )]
        semantic = [RetrievedClaim(
            claim_id="c2", claim_type="works_with",
            subject_id="s2", subject_name="C", object_id="o2",
            object_name="D", confidence=0.8, valid_from=None,
            valid_to=None, status="current", mention_count=3,
            source="semantic",
        )]

        merged = engine._merge_results(graph, semantic)
        assert len(merged) == 2

    def test_overlap_keeps_graph_version(self):
        engine, _, _ = _make_engine()

        graph = [RetrievedClaim(
            claim_id="c1", claim_type="reports_to",
            subject_id="s1", subject_name="Alice",
            object_id="o1", object_name="Bob",
            confidence=0.9, valid_from="2001-01-01",
            valid_to=None, status="current", mention_count=5,
            relevance_score=1.0, source="graph",
        )]
        semantic = [RetrievedClaim(
            claim_id="c1", claim_type="reports_to",
            subject_id="s1", subject_name="",
            object_id="o1", object_name="",
            confidence=0.9, valid_from="2001-01-01",
            valid_to=None, status="", mention_count=0,
            relevance_score=0.85, source="semantic",
        )]

        merged = engine._merge_results(graph, semantic)
        assert len(merged) == 1
        assert merged[0].subject_name == "Alice"  # graph version kept
        assert merged[0].source == "both"
        assert merged[0].relevance_score == 1.0  # max of 1.0 and 0.85

    def test_empty_inputs(self):
        engine, _, _ = _make_engine()
        merged = engine._merge_results([], [])
        assert len(merged) == 0


class TestRanking:
    """Test _rank_results scoring logic."""

    def test_higher_confidence_ranks_higher(self):
        engine, _, _ = _make_engine()

        claims = [
            RetrievedClaim(
                claim_id="c1", claim_type="reports_to",
                subject_id="s1", subject_name="A",
                object_id="o1", object_name="B",
                confidence=0.5, valid_from=None, valid_to=None,
                status="current", mention_count=1,
                relevance_score=1.0, source="graph",
            ),
            RetrievedClaim(
                claim_id="c2", claim_type="reports_to",
                subject_id="s2", subject_name="C",
                object_id="o2", object_name="D",
                confidence=0.95, valid_from=None, valid_to=None,
                status="current", mention_count=1,
                relevance_score=1.0, source="graph",
            ),
        ]

        ranked = engine._rank_results(claims)
        assert ranked[0].claim_id == "c2"  # higher confidence

    def test_both_source_gets_boost(self):
        engine, _, _ = _make_engine()

        claims = [
            RetrievedClaim(
                claim_id="c1", claim_type="reports_to",
                subject_id="s1", subject_name="A",
                object_id="o1", object_name="B",
                confidence=0.9, valid_from=None, valid_to=None,
                status="current", mention_count=1,
                relevance_score=1.0, source="graph",
            ),
            RetrievedClaim(
                claim_id="c2", claim_type="reports_to",
                subject_id="s2", subject_name="C",
                object_id="o2", object_name="D",
                confidence=0.9, valid_from=None, valid_to=None,
                status="current", mention_count=1,
                relevance_score=1.0, source="both",
            ),
        ]

        ranked = engine._rank_results(claims)
        assert ranked[0].claim_id == "c2"  # "both" gets 1.2x boost


class TestClarification:
    """Test clarification handling."""

    def test_pure_clarification_returns_empty_claims(self):
        engine, _, _ = _make_engine()

        plan = _make_plan(
            needs_clarification=True,
            clarification_reason="Too ambiguous",
            entities=[
                ResolvedEntity("Smith", None, None, "person", 0.0, [
                    {"id": "p1", "name": "John Smith"},
                    {"id": "p2", "name": "Jane Smith"},
                ])
            ],
        )

        pack = engine.retrieve(plan)
        assert len(pack.claims) == 0
        assert pack.clarification is not None
        assert "Too ambiguous" in pack.clarification.message

    def test_clarification_with_resolved_entity_still_retrieves(self):
        engine, driver, _ = _make_engine()

        # Mock Neo4j to return a claim
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.run.return_value = mock_result
        driver.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        plan = _make_plan(
            needs_clarification=True,
            clarification_reason="Multiple matches",
            entities=[
                ResolvedEntity(
                    "Sally Beck",
                    "person:beck-sally:...",
                    "Sally Beck",
                    "person", 0.9,
                    [{"id": "p2", "name": "Other Beck"}],
                )
            ],
        )

        pack = engine.retrieve(plan)
        # Should still attempt retrieval since entity is resolved
        assert pack.clarification is not None


class TestFormatDate:
    """Test the _format_date helper."""

    def test_none(self):
        assert _format_date(None) is None

    def test_string(self):
        assert _format_date("2001-03-01") == "2001-03-01"

    def test_iso_format_object(self):
        mock_date = MagicMock()
        mock_date.iso_format.return_value = "2001-03-01"
        assert _format_date(mock_date) == "2001-03-01"