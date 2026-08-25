"""
Unit tests for Health Monitor.

Run with:
    cd ~/Layer_10_Project2/backend
    python -m pytest tests/test_health_monitor.py -v
"""

import pytest
import sys
from pathlib import Path

from neo4j import GraphDatabase

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.graph.health_monitor import HealthMonitor

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
def monitor():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
    except Exception:
        pytest.skip("Neo4j not available")
    data_dir = PROJECT_ROOT / "data" / "processed"
    m = HealthMonitor(driver, data_dir=data_dir)
    yield m
    driver.close()


class TestGraphSize:
    def test_returns_nodes_and_edges(self, monitor):
        size = monitor.graph_size()
        assert "nodes" in size
        assert "edges" in size
        assert size["nodes"]["TOTAL"] > 0
        assert size["edges"]["TOTAL"] > 0

    def test_all_node_types_present(self, monitor):
        nodes = monitor.graph_size()["nodes"]
        for label in ["Person", "Organization", "Message", "Claim", "Evidence"]:
            assert label in nodes
            assert nodes[label] > 0


class TestClaimQuality:
    def test_has_confidence_stats(self, monitor):
        quality = monitor.claim_quality()
        assert "average_confidence" in quality
        assert quality["average_confidence"] > 0
        assert quality["average_confidence"] <= 1.0

    def test_has_distribution(self, monitor):
        quality = monitor.claim_quality()
        assert "confidence_distribution" in quality
        assert len(quality["confidence_distribution"]) > 0

    def test_has_evidence_coverage(self, monitor):
        quality = monitor.claim_quality()
        ec = quality["evidence_coverage"]
        assert "no_evidence" in ec
        assert "single_evidence" in ec
        assert "multi_evidence" in ec

    def test_has_verification_rate(self, monitor):
        quality = monitor.claim_quality()
        ev = quality["evidence_verification"]
        assert ev["verification_rate"] > 0


class TestTemporalHealth:
    def test_has_status_distribution(self, monitor):
        health = monitor.temporal_health()
        assert "claims_by_status" in health
        assert "current" in health["claims_by_status"]

    def test_has_date_range(self, monitor):
        health = monitor.temporal_health()
        assert health["date_range"]["earliest"] is not None
        assert health["date_range"]["latest"] is not None


class TestDataQuality:
    def test_has_quality_score(self, monitor):
        dq = monitor.data_quality()
        assert "quality_score" in dq
        assert 0 <= dq["quality_score"] <= 100

    def test_tracks_missing_edges(self, monitor):
        dq = monitor.data_quality()
        assert "claims_without_subject" in dq
        assert "claims_without_evidence" in dq


class TestFullReport:
    def test_full_report_has_all_sections(self, monitor):
        report = monitor.full_health_report()
        assert "timestamp" in report
        assert "graph_size" in report
        assert "claim_quality" in report
        assert "temporal_health" in report
        assert "access_levels" in report
        assert "entity_stats" in report
        assert "data_quality" in report
        assert "pipeline_status" in report


class TestPipelineStatus:
    def test_checks_required_files(self, monitor):
        status = monitor.pipeline_status()
        assert "extractions_final.jsonl" in status
        assert "resolved_claims.jsonl" in status
        assert status["extractions_final.jsonl"]["exists"] is True