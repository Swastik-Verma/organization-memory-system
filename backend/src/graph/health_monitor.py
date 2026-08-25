"""
Day 27 — Health Monitoring

Comprehensive metrics about the knowledge graph's quality and the
pipeline's health. Feeds the frontend health dashboard (Day 42) and
provides baseline measurements for detecting degradation.

Metrics categories:
  1. Graph size — node and edge counts by type
  2. Claim quality — confidence distribution, evidence coverage
  3. Temporal health — status distribution, supersession stats
  4. Access level distribution — permission layer stats
  5. Entity stats — merge counts, resolution coverage
  6. Data quality — orphan nodes, missing edges, unresolved references
  7. Pipeline status — last update, processing summary

Usage:
    from src.graph.health_monitor import HealthMonitor
    monitor = HealthMonitor(driver)
    report = monitor.full_health_report()
    # or individual sections:
    size = monitor.graph_size()
    quality = monitor.claim_quality()
"""

import json
from datetime import datetime
from pathlib import Path

from neo4j import Driver


class HealthMonitor:
    """
    Collects and reports health metrics for the knowledge graph.
    """

    def __init__(self, driver: Driver, data_dir: Path | None = None):
        self.driver = driver
        self.data_dir = data_dir  # For pipeline file stats

    # ==============================================================
    # FULL REPORT
    # ==============================================================

    def full_health_report(self) -> dict:
        """
        Collect all health metrics into a single report.
        Returns a dict with all sections.
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "graph_size": self.graph_size(),
            "claim_quality": self.claim_quality(),
            "temporal_health": self.temporal_health(),
            "access_levels": self.access_level_distribution(),
            "entity_stats": self.entity_stats(),
            "data_quality": self.data_quality(),
        }

        if self.data_dir:
            report["pipeline_status"] = self.pipeline_status()

        return report

    # ==============================================================
    # 1. GRAPH SIZE
    # ==============================================================

    def graph_size(self) -> dict:
        """Count nodes and edges by type."""
        with self.driver.session() as session:
            # Node counts
            node_counts = {}
            result = session.run("""
                CALL {
                    MATCH (p:Person) RETURN 'Person' AS label, count(p) AS cnt
                    UNION ALL
                    MATCH (o:Organization) RETURN 'Organization' AS label, count(o) AS cnt
                    UNION ALL
                    MATCH (m:Message) RETURN 'Message' AS label, count(m) AS cnt
                    UNION ALL
                    MATCH (d:Deal) RETURN 'Deal' AS label, count(d) AS cnt
                    UNION ALL
                    MATCH (d:Decision) RETURN 'Decision' AS label, count(d) AS cnt
                    UNION ALL
                    MATCH (c:Claim) RETURN 'Claim' AS label, count(c) AS cnt
                    UNION ALL
                    MATCH (e:Evidence) RETURN 'Evidence' AS label, count(e) AS cnt
                }
                RETURN label, cnt ORDER BY cnt DESC
            """)
            total_nodes = 0
            for record in result:
                node_counts[record["label"]] = record["cnt"]
                total_nodes += record["cnt"]
            node_counts["TOTAL"] = total_nodes

            # Edge counts
            edge_counts = {}
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) AS rel_type, count(r) AS cnt
                ORDER BY cnt DESC
            """)
            total_edges = 0
            for record in result:
                edge_counts[record["rel_type"]] = record["cnt"]
                total_edges += record["cnt"]
            edge_counts["TOTAL"] = total_edges

            return {
                "nodes": node_counts,
                "edges": edge_counts,
            }

    # ==============================================================
    # 2. CLAIM QUALITY
    # ==============================================================

    def claim_quality(self) -> dict:
        """
        Metrics about claim confidence and evidence coverage.
        """
        with self.driver.session() as session:
            stats = {}

            # Average and median confidence
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.is_deleted = false AND c.confidence IS NOT NULL
                RETURN avg(c.confidence) AS avg_confidence,
                       min(c.confidence) AS min_confidence,
                       max(c.confidence) AS max_confidence,
                       count(c) AS total
            """)
            record = result.single()
            stats["average_confidence"] = round(record["avg_confidence"], 4) if record["avg_confidence"] else 0
            stats["min_confidence"] = record["min_confidence"]
            stats["max_confidence"] = record["max_confidence"]
            stats["total_claims"] = record["total"]

            # Confidence distribution (buckets)
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.is_deleted = false AND c.confidence IS NOT NULL
                RETURN
                    CASE
                        WHEN c.confidence >= 0.9 THEN '0.90-1.00'
                        WHEN c.confidence >= 0.7 THEN '0.70-0.89'
                        WHEN c.confidence >= 0.5 THEN '0.50-0.69'
                        WHEN c.confidence >= 0.3 THEN '0.30-0.49'
                        ELSE '0.00-0.29'
                    END AS bucket,
                    count(c) AS cnt
                ORDER BY bucket DESC
            """)
            stats["confidence_distribution"] = {
                record["bucket"]: record["cnt"] for record in result
            }

            # Claims by type
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.is_deleted = false
                RETURN c.claim_type AS claim_type, count(c) AS cnt
                ORDER BY cnt DESC
            """)
            stats["claims_by_type"] = {
                record["claim_type"]: record["cnt"] for record in result
            }

            # Evidence coverage
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.is_deleted = false
                OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(e:Evidence)
                WHERE e.is_deleted = false
                WITH c, count(e) AS ev_count
                RETURN
                    sum(CASE WHEN ev_count = 0 THEN 1 ELSE 0 END) AS no_evidence,
                    sum(CASE WHEN ev_count = 1 THEN 1 ELSE 0 END) AS single_evidence,
                    sum(CASE WHEN ev_count > 1 THEN 1 ELSE 0 END) AS multi_evidence,
                    avg(ev_count) AS avg_evidence_per_claim
            """)
            record = result.single()
            stats["evidence_coverage"] = {
                "no_evidence": record["no_evidence"],
                "single_evidence": record["single_evidence"],
                "multi_evidence": record["multi_evidence"],
                "avg_evidence_per_claim": round(record["avg_evidence_per_claim"], 2) if record["avg_evidence_per_claim"] else 0,
            }

            # Evidence verification rate
            result = session.run("""
                MATCH (e:Evidence)
                WHERE e.is_deleted = false
                RETURN
                    count(e) AS total,
                    sum(CASE WHEN e.evidence_verified = true THEN 1 ELSE 0 END) AS verified,
                    sum(CASE WHEN e.evidence_verified = false THEN 1 ELSE 0 END) AS unverified,
                    sum(CASE WHEN e.evidence_verified IS NULL THEN 1 ELSE 0 END) AS unknown
            """)
            record = result.single()
            total_ev = record["total"]
            verified = record["verified"]
            stats["evidence_verification"] = {
                "total": total_ev,
                "verified": verified,
                "unverified": record["unverified"],
                "unknown": record["unknown"],
                "verification_rate": round(verified / total_ev * 100, 1) if total_ev > 0 else 0,
            }

            return stats

    # ==============================================================
    # 3. TEMPORAL HEALTH
    # ==============================================================

    def temporal_health(self) -> dict:
        """
        Status distribution and supersession statistics.
        """
        with self.driver.session() as session:
            stats = {}

            # Claims by status
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.is_deleted = false
                RETURN c.status AS status, count(c) AS cnt
                ORDER BY cnt DESC
            """)
            stats["claims_by_status"] = {
                record["status"]: record["cnt"] for record in result
            }

            # Supersession chains
            result = session.run("""
                MATCH (new:Claim)-[:SUPERSEDES]->(old:Claim)
                RETURN count(*) AS supersession_edges
            """)
            stats["supersession_edges"] = result.single()["supersession_edges"]

            # Conflict count
            result = session.run("""
                MATCH (c1:Claim)-[:CONFLICTS_WITH]->(c2:Claim)
                WHERE c1.is_deleted = false AND c2.is_deleted = false
                RETURN count(*) / 2 AS conflict_pairs
            """)
            stats["conflict_pairs"] = result.single()["conflict_pairs"]

            # Claims with closed validity windows
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.is_deleted = false AND c.valid_to IS NOT NULL
                RETURN count(c) AS closed_windows
            """)
            stats["claims_with_closed_windows"] = result.single()["closed_windows"]

            # Undated claims
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.is_deleted = false AND c.valid_from IS NULL
                RETURN count(c) AS undated
            """)
            stats["undated_claims"] = result.single()["undated"]

            # Date range
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.is_deleted = false AND c.valid_from IS NOT NULL
                RETURN min(c.valid_from) AS earliest, max(c.valid_from) AS latest
            """)
            record = result.single()
            stats["date_range"] = {
                "earliest": record["earliest"],
                "latest": record["latest"],
            }

            return stats

    # ==============================================================
    # 4. ACCESS LEVEL DISTRIBUTION
    # ==============================================================

    def access_level_distribution(self) -> dict:
        """Access level counts per content type."""
        level_names = {1: "PUBLIC", 2: "INTERNAL", 3: "CONFIDENTIAL", 4: "RESTRICTED"}

        with self.driver.session() as session:
            stats = {}
            for label in ["Claim", "Evidence", "Message", "Decision"]:
                result = session.run(f"""
                    MATCH (n:{label})
                    WHERE n.is_deleted = false
                    RETURN n.access_level AS level, count(n) AS cnt
                    ORDER BY level
                """)
                dist = {}
                for record in result:
                    level = record["level"]
                    name = level_names.get(level, f"UNKNOWN({level})")
                    dist[name] = record["cnt"]
                stats[label] = dist

            return stats

    # ==============================================================
    # 5. ENTITY STATS
    # ==============================================================

    def entity_stats(self) -> dict:
        """Entity counts and resolution statistics."""
        with self.driver.session() as session:
            stats = {}

            # Person stats
            result = session.run("""
                MATCH (p:Person)
                WHERE p.is_deleted = false
                RETURN count(p) AS total,
                       avg(p.mention_count) AS avg_mentions,
                       max(p.mention_count) AS max_mentions,
                       sum(size(p.aliases)) AS total_aliases,
                       sum(size(p.emails)) AS total_emails
            """)
            record = result.single()
            stats["persons"] = {
                "total": record["total"],
                "avg_mentions": round(record["avg_mentions"], 1) if record["avg_mentions"] else 0,
                "max_mentions": record["max_mentions"],
                "total_aliases": record["total_aliases"],
                "total_emails": record["total_emails"],
            }

            # Organization stats
            result = session.run("""
                MATCH (o:Organization)
                WHERE o.is_deleted = false
                RETURN count(o) AS total,
                       avg(o.mention_count) AS avg_mentions
            """)
            record = result.single()
            stats["organizations"] = {
                "total": record["total"],
                "avg_mentions": round(record["avg_mentions"], 1) if record["avg_mentions"] else 0,
            }

            # Org type distribution
            result = session.run("""
                MATCH (o:Organization)
                WHERE o.is_deleted = false
                RETURN o.org_type AS org_type, count(o) AS cnt
                ORDER BY cnt DESC
            """)
            stats["org_types"] = {
                (record["org_type"] or "null"): record["cnt"] for record in result
            }

            # Top entities by mention count
            result = session.run("""
                MATCH (p:Person)
                WHERE p.is_deleted = false
                RETURN p.canonical_name AS name, p.mention_count AS mentions
                ORDER BY mentions DESC
                LIMIT 10
            """)
            stats["top_persons"] = [
                {"name": r["name"], "mentions": r["mentions"]} for r in result
            ]

            return stats

    # ==============================================================
    # 6. DATA QUALITY
    # ==============================================================

    def data_quality(self) -> dict:
        """
        Detect data quality issues — orphan nodes, missing edges,
        and structural problems.
        """
        with self.driver.session() as session:
            issues = {}

            # Claims without SUBJECT edge
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.is_deleted = false AND NOT (c)-[:SUBJECT]->()
                RETURN count(c) AS cnt
            """)
            issues["claims_without_subject"] = result.single()["cnt"]

            # Claims without OBJECT edge
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.is_deleted = false AND NOT (c)-[:OBJECT]->()
                RETURN count(c) AS cnt
            """)
            issues["claims_without_object"] = result.single()["cnt"]

            # Claims without any evidence
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.is_deleted = false AND NOT (c)-[:SUPPORTED_BY]->()
                RETURN count(c) AS cnt
            """)
            issues["claims_without_evidence"] = result.single()["cnt"]

            # Evidence without FROM_MESSAGE
            result = session.run("""
                MATCH (e:Evidence)
                WHERE e.is_deleted = false AND NOT (e)-[:FROM_MESSAGE]->()
                RETURN count(e) AS cnt
            """)
            issues["evidence_without_message"] = result.single()["cnt"]

            # Messages without SENT_BY
            result = session.run("""
                MATCH (m:Message)
                WHERE m.is_deleted = false AND NOT (m)-[:SENT_BY]->()
                RETURN count(m) AS cnt
            """)
            issues["messages_without_sender"] = result.single()["cnt"]

            # Decisions without MADE_BY
            result = session.run("""
                MATCH (d:Decision)
                WHERE d.is_deleted = false AND NOT (d)-[:MADE_BY]->()
                RETURN count(d) AS cnt
            """)
            issues["decisions_without_maker"] = result.single()["cnt"]

            # Decisions with unresolved affects
            result = session.run("""
                MATCH (d:Decision)
                WHERE d.is_deleted = false AND size(d.affects_unresolved) > 0
                RETURN count(d) AS cnt,
                       sum(size(d.affects_unresolved)) AS total_unresolved
            """)
            record = result.single()
            issues["decisions_with_unresolved_affects"] = record["cnt"]
            issues["total_unresolved_affects_strings"] = record["total_unresolved"]

            # Soft-deleted content
            result = session.run("""
                CALL {
                    MATCH (n:Person) WHERE n.is_deleted = true RETURN count(n) AS cnt
                    UNION ALL
                    MATCH (n:Organization) WHERE n.is_deleted = true RETURN count(n) AS cnt
                    UNION ALL
                    MATCH (n:Claim) WHERE n.is_deleted = true RETURN count(n) AS cnt
                    UNION ALL
                    MATCH (n:Evidence) WHERE n.is_deleted = true RETURN count(n) AS cnt
                    UNION ALL
                    MATCH (n:Message) WHERE n.is_deleted = true RETURN count(n) AS cnt
                }
                RETURN sum(cnt) AS total_deleted
            """)
            issues["soft_deleted_nodes"] = result.single()["total_deleted"]

            # Calculate overall quality score (0-100)
            total_claims = issues["claims_without_subject"] + issues["claims_without_object"] + issues["claims_without_evidence"]
            # Get total claims for percentage
            result = session.run("""
                MATCH (c:Claim) WHERE c.is_deleted = false RETURN count(c) AS total
            """)
            total = result.single()["total"]
            if total > 0:
                issue_rate = total_claims / total
                issues["quality_score"] = round((1 - issue_rate) * 100, 1)
            else:
                issues["quality_score"] = 0

            return issues

    # ==============================================================
    # 7. PIPELINE STATUS (from files)
    # ==============================================================

    def pipeline_status(self) -> dict:
        """
        Check pipeline data files for freshness and completeness.
        Requires data_dir to be set.
        """
        if not self.data_dir:
            return {"error": "data_dir not configured"}

        status = {}
        expected_files = {
            "extractions_final.jsonl": "Enriched extractions",
            "resolved_claims.jsonl": "Deduplicated claims",
            "entity_resolution_fuzzy.json": "Canonical entities",
            "resolution_map.json": "Name resolution map",
            "duplicate_ids.json": "Duplicate email IDs",
            "extraction_subset.jsonl": "Source emails",
        }

        for filename, description in expected_files.items():
            path = self.data_dir / filename
            if path.exists():
                stat = path.stat()
                line_count = None
                if filename.endswith(".jsonl"):
                    with open(path) as f:
                        line_count = sum(1 for _ in f)
                elif filename.endswith(".json"):
                    data = json.loads(path.read_text())
                    if isinstance(data, list):
                        line_count = len(data)
                    elif isinstance(data, dict):
                        line_count = len(data)

                status[filename] = {
                    "exists": True,
                    "description": description,
                    "size_mb": round(stat.st_size / 1024 / 1024, 2),
                    "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "record_count": line_count,
                }
            else:
                status[filename] = {
                    "exists": False,
                    "description": description,
                }

        return status