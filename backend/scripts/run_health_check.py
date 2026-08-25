"""
Day 27 — Health Monitoring Runner

Generates a comprehensive health report for the knowledge graph.

Usage:
    cd ~/Layer_10_Project2/backend
    source venv/bin/activate
    python scripts/run_health_check.py

    Save report to file:
    python scripts/run_health_check.py --save
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from neo4j import GraphDatabase

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"

sys.path.insert(0, str(BACKEND_DIR))

from src.graph.health_monitor import HealthMonitor

# --- Neo4j connection ---
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neo4j"

def load_env():
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


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true",
                        help="Save report to data/processed/health_report.json")
    args = parser.parse_args()

    load_env()

    print("Connecting to Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print("Connected.\n")

    monitor = HealthMonitor(driver, data_dir=DATA_DIR)

    # Generate full report
    print("Generating health report...")
    report = monitor.full_health_report()

    # ---- 1. Graph Size ----
    print_section("1. Graph Size")
    nodes = report["graph_size"]["nodes"]
    print("  Nodes:")
    for label, count in nodes.items():
        marker = "  ═══" if label == "TOTAL" else ""
        print(f"    {label:20} {count:>8,}{marker}")

    edges = report["graph_size"]["edges"]
    print("\n  Edges:")
    for rel_type, count in edges.items():
        marker = "  ═══" if rel_type == "TOTAL" else ""
        print(f"    {rel_type:20} {count:>8,}{marker}")

    # ---- 2. Claim Quality ----
    print_section("2. Claim Quality")
    cq = report["claim_quality"]
    print(f"  Average confidence: {cq['average_confidence']}")
    print(f"  Min / Max: {cq['min_confidence']} / {cq['max_confidence']}")
    print(f"\n  Confidence distribution:")
    for bucket, count in sorted(cq["confidence_distribution"].items(), reverse=True):
        pct = count / cq["total_claims"] * 100 if cq["total_claims"] > 0 else 0
        bar = "█" * int(pct / 2)
        print(f"    {bucket}: {count:>5,} ({pct:5.1f}%) {bar}")

    print(f"\n  Claims by type:")
    for ct, count in cq["claims_by_type"].items():
        print(f"    {ct:25} {count:>5,}")

    ec = cq["evidence_coverage"]
    print(f"\n  Evidence coverage:")
    print(f"    No evidence:     {ec['no_evidence']:>5,}")
    print(f"    Single evidence: {ec['single_evidence']:>5,}")
    print(f"    Multi evidence:  {ec['multi_evidence']:>5,}")
    print(f"    Avg per claim:   {ec['avg_evidence_per_claim']}")

    ev = cq["evidence_verification"]
    print(f"\n  Evidence verification:")
    print(f"    Total:      {ev['total']:>5,}")
    print(f"    Verified:   {ev['verified']:>5,} ({ev['verification_rate']}%)")
    print(f"    Unverified: {ev['unverified']:>5,}")

    # ---- 3. Temporal Health ----
    print_section("3. Temporal Health")
    th = report["temporal_health"]
    print("  Claims by status:")
    for status, count in th["claims_by_status"].items():
        print(f"    {status:15} {count:>5,}")
    print(f"\n  Supersession edges: {th['supersession_edges']}")
    print(f"  Conflict pairs: {th['conflict_pairs']}")
    print(f"  Closed validity windows: {th['claims_with_closed_windows']}")
    print(f"  Undated claims: {th['undated_claims']}")
    print(f"  Date range: {th['date_range']['earliest']} to {th['date_range']['latest']}")

    # ---- 4. Access Levels ----
    print_section("4. Access Level Distribution")
    for content_type, dist in report["access_levels"].items():
        print(f"\n  {content_type}:")
        for level_name, count in dist.items():
            print(f"    {level_name:15} {count:>8,}")

    # ---- 5. Entity Stats ----
    print_section("5. Entity Statistics")
    es = report["entity_stats"]
    p = es["persons"]
    print(f"  Persons: {p['total']:,}")
    print(f"    Avg mentions: {p['avg_mentions']}")
    print(f"    Max mentions: {p['max_mentions']}")
    print(f"    Total aliases: {p['total_aliases']}")
    print(f"    Total emails: {p['total_emails']}")

    o = es["organizations"]
    print(f"\n  Organizations: {o['total']:,}")
    print(f"    Avg mentions: {o['avg_mentions']}")

    print(f"\n  Org types:")
    for ot, count in es["org_types"].items():
        print(f"    {ot:25} {count:>5,}")

    print(f"\n  Top 10 persons by mentions:")
    for i, person in enumerate(es["top_persons"], 1):
        print(f"    {i:2}. {person['name']:30} {person['mentions']:>5,}")

    # ---- 6. Data Quality ----
    print_section("6. Data Quality")
    dq = report["data_quality"]
    print(f"  Quality score: {dq['quality_score']}/100")
    print(f"\n  Issues:")
    print(f"    Claims without SUBJECT edge:      {dq['claims_without_subject']:>5}")
    print(f"    Claims without OBJECT edge:        {dq['claims_without_object']:>5}")
    print(f"    Claims without evidence:           {dq['claims_without_evidence']:>5}")
    print(f"    Evidence without source message:   {dq['evidence_without_message']:>5}")
    print(f"    Messages without sender:           {dq['messages_without_sender']:>5}")
    print(f"    Decisions without maker:           {dq['decisions_without_maker']:>5}")
    print(f"    Decisions with unresolved affects: {dq['decisions_with_unresolved_affects']:>5}")
    print(f"    Total unresolved affects strings:  {dq['total_unresolved_affects_strings']:>5}")
    print(f"    Soft-deleted nodes:                {dq['soft_deleted_nodes']:>5}")

    # ---- 7. Pipeline Status ----
    if "pipeline_status" in report:
        print_section("7. Pipeline Status")
        for filename, info in report["pipeline_status"].items():
            if info["exists"]:
                print(f"  {filename}")
                print(f"    Size: {info['size_mb']} MB | "
                      f"Records: {info['record_count']:,} | "
                      f"Modified: {info['last_modified'][:19]}")
            else:
                print(f"  {filename}: MISSING")

    # ---- Save ----
    if args.save:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = DATA_DIR / f"health_report_{timestamp}.json"
        save_path.write_text(json.dumps(report, indent=2, default=str))
        print(f"\n  Report saved to {save_path}")

    driver.close()
    print("\n\nDone.")


if __name__ == "__main__":
    main()