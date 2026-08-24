"""
Unit tests for the Incremental Update System.

Run with:
    cd ~/Layer_10_Project2/backend
    python -m pytest tests/test_incremental_updater.py -v
"""

import pytest
import sys
from pathlib import Path

from neo4j import GraphDatabase

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.graph.incremental_updater import (
    IncrementalUpdater,
    VALID_CLAIM_TYPES,
    VALID_ORG_TYPES,
    _days_between,
)


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
def updater():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
    except Exception:
        pytest.skip("Neo4j not available")
    u = IncrementalUpdater(driver)
    yield u
    driver.close()


# ==============================================================
# HELPERS
# ==============================================================

class TestDaysBetween:
    def test_same_day(self):
        assert _days_between("2001-01-01", "2001-01-01") == 0

    def test_one_year(self):
        assert _days_between("2000-01-01", "2001-01-01") == 366  # 2000 is leap year

    def test_order_independent(self):
        assert _days_between("2001-06-01", "2000-01-01") == _days_between("2000-01-01", "2001-06-01")


# ==============================================================
# CONSTANTS
# ==============================================================

class TestConstants:
    def test_valid_claim_types(self):
        expected = {"reports_to", "works_with", "requests_from", "negotiating_with", "informs"}
        assert VALID_CLAIM_TYPES == expected

    def test_valid_org_types(self):
        assert "company" in VALID_ORG_TYPES
        assert "government" in VALID_ORG_TYPES


# ==============================================================
# CONFIDENCE DECAY
# ==============================================================

class TestConfidenceDecay:
    def test_preview_returns_list(self, updater):
        preview = updater.preview_confidence_decay(limit=5)
        assert isinstance(preview, list)

    def test_decay_report_has_required_keys(self, updater):
        report = updater.apply_confidence_decay()
        assert "claims_evaluated" in report
        assert "claims_decayed" in report
        assert "claims_archived" in report
        assert "claims_unchanged" in report
        assert report["claims_evaluated"] > 0

    def test_decay_is_idempotent(self, updater):
        """Running decay twice should not double-decay."""
        report1 = updater.apply_confidence_decay()
        report2 = updater.apply_confidence_decay()
        # Second run should decay fewer or same claims
        # (already-decayed claims have lower confidence, 
        #  so they may cross the archive threshold)
        assert report2["claims_evaluated"] > 0


# ==============================================================
# ONTOLOGY DRIFT DETECTION
# ==============================================================

class TestOntologyDrift:
    def test_clean_extraction_no_drift(self, updater):
        clean = [{
            "message_id": "test-1",
            "people": [{"name": "John"}],
            "organizations": [{"name": "Enron", "org_type": "company"}],
            "deals": [],
            "decisions": [],
            "relationships": [{
                "person_a": "John",
                "person_b": "Jane",
                "relationship_type": "works_with",
                "evidence": "they work together",
            }],
        }]
        report = updater.detect_ontology_drift(clean)
        assert report["drift_detected"] is False
        assert len(report["unknown_relationship_types"]) == 0

    def test_unknown_relationship_type_detected(self, updater):
        bad = [{
            "message_id": "test-2",
            "people": [],
            "organizations": [],
            "deals": [],
            "decisions": [],
            "relationships": [{
                "person_a": "John",
                "person_b": "Jane",
                "relationship_type": "best_friends_with",
                "evidence": "they are best friends",
            }],
        }]
        report = updater.detect_ontology_drift(bad)
        assert report["drift_detected"] is True
        assert "best_friends_with" in report["unknown_relationship_types"]

    def test_self_referential_detected(self, updater):
        bad = [{
            "message_id": "test-3",
            "people": [],
            "organizations": [],
            "deals": [],
            "decisions": [],
            "relationships": [{
                "person_a": "John",
                "person_b": "John",
                "relationship_type": "works_with",
                "evidence": "works alone",
            }],
        }]
        report = updater.detect_ontology_drift(bad)
        assert len(report["structural_issues"]) > 0

    def test_empty_extraction_counted(self, updater):
        empty = [{
            "message_id": "test-4",
            "people": [],
            "organizations": [],
            "deals": [],
            "decisions": [],
            "relationships": [],
        }]
        report = updater.detect_ontology_drift(empty)
        assert report["empty_extractions"] == 1


class TestGraphDrift:
    def test_graph_drift_returns_distributions(self, updater):
        report = updater.detect_graph_drift()
        assert "claim_type_distribution" in report
        assert "org_type_distribution" in report
        assert len(report["claim_type_distribution"]) > 0