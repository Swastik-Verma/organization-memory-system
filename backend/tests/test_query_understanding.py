"""Tests for the query understanding module."""

import pytest
from unittest.mock import MagicMock, patch
from src.retrieval.query_understanding import (
    QueryUnderstanding,
    QueryPlan,
    QuestionType,
    TimeConstraintType,
    RetrievalStrategy,
    ResolvedEntity,
    TimeConstraint,
)


class TestTimeConstraintBuilding:
    """Test _build_time_constraint logic."""

    def _make_qu(self):
        """Create a QueryUnderstanding with mocked dependencies."""
        with patch("src.retrieval.query_understanding.genai"):
            qu = QueryUnderstanding.__new__(QueryUnderstanding)
            qu.driver = MagicMock()
            qu.client = MagicMock()
            qu.model_name = "test"
            return qu

    def test_none_constraint(self):
        qu = self._make_qu()
        tc = qu._build_time_constraint({"type": "none"})
        assert tc.constraint_type == TimeConstraintType.NONE
        assert tc.date_from is None
        assert tc.date_to is None

    def test_point_constraint(self):
        qu = self._make_qu()
        tc = qu._build_time_constraint({
            "type": "point",
            "date_from": "2001-03-01",
            "raw_text": "March 2001",
        })
        assert tc.constraint_type == TimeConstraintType.POINT
        assert tc.date_from == "2001-03-01"
        assert tc.raw_reference == "March 2001"

    def test_range_constraint(self):
        qu = self._make_qu()
        tc = qu._build_time_constraint({
            "type": "range",
            "date_from": "2000-01-01",
            "date_to": "2001-12-31",
        })
        assert tc.constraint_type == TimeConstraintType.RANGE
        assert tc.date_from == "2000-01-01"
        assert tc.date_to == "2001-12-31"

    def test_invalid_type_defaults_to_none(self):
        qu = self._make_qu()
        tc = qu._build_time_constraint({"type": "whenever"})
        assert tc.constraint_type == TimeConstraintType.NONE

    def test_empty_dict_defaults_to_none(self):
        qu = self._make_qu()
        tc = qu._build_time_constraint({})
        assert tc.constraint_type == TimeConstraintType.NONE


class TestAmbiguityDetection:
    """Test _detect_ambiguity logic."""

    def _make_qu(self):
        with patch("src.retrieval.query_understanding.genai"):
            qu = QueryUnderstanding.__new__(QueryUnderstanding)
            qu.driver = MagicMock()
            qu.client = MagicMock()
            qu.model_name = "test"
            return qu

    def test_llm_flagged_ambiguity(self):
        qu = self._make_qu()
        parsed = {"is_ambiguous": True, "ambiguity_reason": "too vague"}
        result, reason = qu._detect_ambiguity(parsed, [])
        assert result is True
        assert "too vague" in reason

    def test_unresolved_entity_triggers_clarification(self):
        qu = self._make_qu()
        parsed = {"is_ambiguous": False}
        entities = [
            ResolvedEntity(
                raw_name="John Doe",
                canonical_id=None,
                canonical_name=None,
                entity_type="person",
                confidence=0.0,
            )
        ]
        result, reason = qu._detect_ambiguity(parsed, entities)
        assert result is True
        assert "John Doe" in reason

    def test_low_confidence_triggers_clarification(self):
        qu = self._make_qu()
        parsed = {"is_ambiguous": False}
        entities = [
            ResolvedEntity(
                raw_name="Smith",
                canonical_id="person:smith-john:...",
                canonical_name="John Smith",
                entity_type="person",
                confidence=0.5,
                alternatives=[
                    {"name": "Jane Smith"},
                    {"name": "Bob Smith"},
                ],
            )
        ]
        result, reason = qu._detect_ambiguity(parsed, entities)
        assert result is True
        assert "Smith" in reason

    def test_high_confidence_no_clarification(self):
        qu = self._make_qu()
        parsed = {"is_ambiguous": False}
        entities = [
            ResolvedEntity(
                raw_name="Sally Beck",
                canonical_id="person:beck-sally:...",
                canonical_name="Sally Beck",
                entity_type="person",
                confidence=1.0,
            )
        ]
        result, reason = qu._detect_ambiguity(parsed, entities)
        assert result is False
        assert reason is None


class TestStrategySelection:
    """Test _choose_strategy logic."""

    def _make_qu(self):
        with patch("src.retrieval.query_understanding.genai"):
            qu = QueryUnderstanding.__new__(QueryUnderstanding)
            qu.driver = MagicMock()
            qu.client = MagicMock()
            qu.model_name = "test"
            return qu

    def test_resolved_entity_only(self):
        """Entity found, no semantic keywords → GRAPH."""
        qu = self._make_qu()
        entities = [
            ResolvedEntity("Sally Beck", "person:beck", "Sally Beck", "person", 1.0)
        ]
        strategy = qu._choose_strategy(entities, TimeConstraint(TimeConstraintType.NONE), {})
        assert strategy == RetrievalStrategy.GRAPH

    def test_semantic_keywords_only(self):
        """No entities, has semantic keywords → SEMANTIC."""
        qu = self._make_qu()
        strategy = qu._choose_strategy(
            [],
            TimeConstraint(TimeConstraintType.NONE),
            {"semantic_keywords": "California energy prices"},
        )
        assert strategy == RetrievalStrategy.SEMANTIC

    def test_entity_plus_semantic(self):
        """Entity found + semantic keywords → HYBRID."""
        qu = self._make_qu()
        entities = [
            ResolvedEntity("Sally Beck", "person:beck", "Sally Beck", "person", 1.0)
        ]
        strategy = qu._choose_strategy(
            entities,
            TimeConstraint(TimeConstraintType.NONE),
            {"semantic_keywords": "management responsibilities"},
        )
        assert strategy == RetrievalStrategy.HYBRID

    def test_unresolved_entity_falls_to_semantic(self):
        """Entity mentioned but not found → SEMANTIC fallback."""
        qu = self._make_qu()
        entities = [
            ResolvedEntity("Unknown Person", None, None, "person", 0.0)
        ]
        strategy = qu._choose_strategy(
            entities,
            TimeConstraint(TimeConstraintType.NONE),
            {},
        )
        assert strategy == RetrievalStrategy.SEMANTIC

    def test_empty_everything_defaults_hybrid(self):
        """Nothing at all → HYBRID as safe default."""
        qu = self._make_qu()
        strategy = qu._choose_strategy(
            [],
            TimeConstraint(TimeConstraintType.NONE),
            {},
        )
        assert strategy == RetrievalStrategy.HYBRID


class TestQuestionTypeParsing:
    """Test _parse_question_type."""

    def _make_qu(self):
        with patch("src.retrieval.query_understanding.genai"):
            qu = QueryUnderstanding.__new__(QueryUnderstanding)
            qu.driver = MagicMock()
            qu.client = MagicMock()
            qu.model_name = "test"
            return qu

    def test_valid_types(self):
        qu = self._make_qu()
        assert qu._parse_question_type("who") == QuestionType.WHO
        assert qu._parse_question_type("what") == QuestionType.WHAT
        assert qu._parse_question_type("history") == QuestionType.HISTORY
        assert qu._parse_question_type("current") == QuestionType.CURRENT
        assert qu._parse_question_type("comparison") == QuestionType.COMPARISON

    def test_case_insensitive(self):
        qu = self._make_qu()
        assert qu._parse_question_type("WHO") == QuestionType.WHO
        assert qu._parse_question_type("History") == QuestionType.HISTORY

    def test_invalid_defaults_to_what(self):
        qu = self._make_qu()
        assert qu._parse_question_type("gibberish") == QuestionType.WHAT
        assert qu._parse_question_type("") == QuestionType.WHAT