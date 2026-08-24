"""
Unit tests for the Temporal Query Engine.

These tests require a running Neo4j instance with loaded data.
They verify query logic, not data correctness.

Run with:
    cd ~/Layer_10_Project2/backend
    python -m pytest tests/test_temporal_queries.py -v
"""

import pytest
import sys
from pathlib import Path

from neo4j import GraphDatabase

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.graph.temporal_queries import TemporalQueryEngine

# --- Connection ---
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neo4j"

def _load_env():
    global NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'\"")
                if key == "NEO4J_URI": NEO4J_URI = value
                elif key == "NEO4J_USER": NEO4J_USER = value
                elif key == "NEO4J_PASSWORD": NEO4J_PASSWORD = value

_load_env()


@pytest.fixture(scope="module")
def engine():
    """Create a TemporalQueryEngine connected to the test database."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
    except Exception:
        pytest.skip("Neo4j not available")
    eng = TemporalQueryEngine(driver)
    yield eng
    driver.close()


class TestFindEntity:
    def test_find_by_partial_name(self, engine):
        results = engine.find_entity("Kean")
        assert len(results) > 0
        assert any("Kean" in r["canonical_name"] for r in results)

    def test_find_returns_entity_type(self, engine):
        results = engine.find_entity("Enron")
        assert len(results) > 0
        types = {r["entity_type"] for r in results}
        assert "organization" in types

    def test_find_nonexistent_returns_empty(self, engine):
        results = engine.find_entity("ZZZZNONEXISTENT12345")
        assert results == []

    def test_find_sorted_by_mention_count(self, engine):
        results = engine.find_entity("Kean")
        if len(results) >= 2:
            assert results[0]["mention_count"] >= results[1]["mention_count"]


class TestGetEntityProfile:
    def test_profile_returns_data(self, engine):
        results = engine.find_entity("Kean")
        assert len(results) > 0
        profile = engine.get_entity_profile(results[0]["id"])
        assert profile is not None
        assert "canonical_name" in profile
        assert "entity_type" in profile

    def test_profile_nonexistent_returns_none(self, engine):
        profile = engine.get_entity_profile("person:nonexistent:fake")
        assert profile is None


class TestGetCurrentState:
    def test_current_state_returns_list(self, engine):
        results = engine.find_entity("Kean")
        assert len(results) > 0
        current = engine.get_current_state(results[0]["id"])
        assert isinstance(current, list)

    def test_current_state_has_required_fields(self, engine):
        results = engine.find_entity("Kean")
        current = engine.get_current_state(results[0]["id"])
        if current:
            row = current[0]
            assert "claim_id" in row
            assert "claim_type" in row
            assert "confidence" in row
            assert "object_name" in row

    def test_current_state_filter_by_type(self, engine):
        results = engine.find_entity("Kean")
        reports = engine.get_current_state(results[0]["id"], claim_type="reports_to")
        for r in reports:
            assert r["claim_type"] == "reports_to"

    def test_current_state_nonexistent_entity(self, engine):
        current = engine.get_current_state("person:nonexistent:fake")
        assert current == []


class TestGetStateAt:
    def test_state_at_returns_list(self, engine):
        results = engine.find_entity("Kean")
        past = engine.get_state_at(results[0]["id"], "2001-06-01")
        assert isinstance(past, list)

    def test_state_at_has_valid_from_before_date(self, engine):
        results = engine.find_entity("Kean")
        past = engine.get_state_at(results[0]["id"], "2001-06-01")
        for r in past:
            assert r["valid_from"] is not None
            assert r["valid_from"] <= "2001-06-01"

    def test_state_at_very_early_date_may_be_empty(self, engine):
        results = engine.find_entity("Kean")
        past = engine.get_state_at(results[0]["id"], "1990-01-01")
        assert isinstance(past, list)


class TestGetFullHistory:
    def test_full_history_includes_current(self, engine):
        results = engine.find_entity("Kean")
        history = engine.get_full_history(results[0]["id"])
        if len(history) > 0:
            statuses = {r["status"] for r in history}
            assert "current" in statuses

    def test_full_history_sorted_chronologically(self, engine):
        results = engine.find_entity("Kean")
        history = engine.get_full_history(results[0]["id"])
        dated = [r for r in history if r["valid_from"] is not None]
        for i in range(1, len(dated)):
            assert dated[i]["valid_from"] >= dated[i-1]["valid_from"]

    def test_full_history_filter_by_type(self, engine):
        results = engine.find_entity("Kean")
        reporting = engine.get_full_history(results[0]["id"], claim_type="reports_to")
        for r in reporting:
            assert r["claim_type"] == "reports_to"


class TestGetEvidence:
    def test_evidence_has_quote(self, engine):
        results = engine.find_entity("Kean")
        current = engine.get_current_state(results[0]["id"])
        if current:
            evidence = engine.get_evidence_for_claim(current[0]["claim_id"])
            if evidence:
                assert evidence[0]["quote"] is not None
                assert len(evidence[0]["quote"]) > 0

    def test_evidence_nonexistent_claim(self, engine):
        evidence = engine.get_evidence_for_claim("claim:nonexistent")
        assert evidence == []


class TestGraphStats:
    def test_stats_has_required_metrics(self, engine):
        stats = engine.get_graph_stats()
        assert "persons" in stats
        assert "total_claims" in stats
        assert "current_claims" in stats
        assert stats["persons"] > 0
        assert stats["total_claims"] > 0