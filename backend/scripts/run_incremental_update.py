"""
Day 25 — Incremental Update System Runner

Demonstrates all three capabilities:
1. Confidence decay preview and application
2. Ontology drift detection (on existing extractions)
3. Graph drift detection (on loaded graph)

Usage:
    cd ~/Layer_10_Project2/backend
    source venv/bin/activate
    python scripts/run_incremental_update.py

Note: Incremental update (new email batch) is demonstrated as a
dry-run concept since we don't have a "new" batch of emails.
The infrastructure is built and tested against the existing data.
"""

import json
import sys
import time
from pathlib import Path

from neo4j import GraphDatabase

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"

sys.path.insert(0, str(BACKEND_DIR))

from src.graph.incremental_updater import IncrementalUpdater

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
    load_env()

    print("Connecting to Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print("Connected.\n")

    updater = IncrementalUpdater(driver)

    # ============================================================
    # 1. CONFIDENCE DECAY — PREVIEW (dry run)
    # ============================================================
    print_section("1. Confidence Decay — Preview (dry run)")
    print("Previewing which claims would be affected by time-based decay...")
    print(f"Reference date: 2002-01-01 (end of meaningful Enron data)")
    print(f"Decay rate: 10% per year without fresh evidence")
    print(f"Archive threshold: 0.30\n")

    preview = updater.preview_confidence_decay(limit=15)
    if preview:
        print(f"  {'Description':<50} {'Original':>8} {'Projected':>10} {'Action'}")
        print(f"  {'-'*50} {'-'*8} {'-'*10} {'-'*15}")
        for row in preview:
            desc = row["description"][:48]
            print(f"  {desc:<50} {row['original_confidence']:>8.2f} "
                  f"{row['projected_confidence']:>10.4f} {row['action']}")
    else:
        print("  No claims would be affected by decay.")
        print("  (This can happen if all claims have evidence within the last year)")

    # ============================================================
    # 2. CONFIDENCE DECAY — APPLY
    # ============================================================
    print_section("2. Confidence Decay — Apply")
    print("Applying confidence decay to the graph...\n")

    start = time.time()
    decay_report = updater.apply_confidence_decay()
    elapsed = time.time() - start

    for key, value in decay_report.items():
        print(f"  {key:25} {value}")
    print(f"\n  Completed in {elapsed:.1f} seconds")

    # ============================================================
    # 3. ONTOLOGY DRIFT — FROM EXTRACTION FILES
    # ============================================================
    print_section("3. Ontology Drift Detection — Extraction Files")
    print("Scanning extractions_final.jsonl for schema violations...\n")

    extractions = []
    final_path = DATA_DIR / "extractions_final.jsonl"
    if final_path.exists():
        with open(final_path) as f:
            for line in f:
                extractions.append(json.loads(line))

    drift_report = updater.detect_ontology_drift(extractions)

    print(f"  Extractions scanned: {drift_report['extractions_scanned']:,}")
    print(f"  Empty extractions: {drift_report['empty_extractions']}")
    print(f"  Drift detected: {drift_report['drift_detected']}")

    if drift_report["unknown_relationship_types"]:
        print(f"\n  Unknown relationship types:")
        for rt, count in sorted(drift_report["unknown_relationship_types"].items(),
                                 key=lambda x: -x[1]):
            print(f"    {rt}: {count}")
    else:
        print(f"  Unknown relationship types: none (closed vocabulary holding)")

    if drift_report["unknown_org_types"]:
        print(f"\n  Org types falling through to 'other' (top 10):")
        sorted_types = sorted(drift_report["unknown_org_types"].items(), key=lambda x: -x[1])
        for ot, count in sorted_types[:10]:
            print(f"    {ot}: {count}")
        if len(sorted_types) > 10:
            print(f"    ... and {len(sorted_types) - 10} more")
    else:
        print(f"  All org types mapped: none falling through to 'other'")

    if drift_report["structural_issues"]:
        print(f"\n  Structural issues: {len(drift_report['structural_issues'])}")
        for issue in drift_report["structural_issues"][:5]:
            print(f"    {issue['issue']} in {issue['message_id'][:40]}...")
    else:
        print(f"  Structural issues: none")

    # ============================================================
    # 4. ONTOLOGY DRIFT — FROM LOADED GRAPH
    # ============================================================
    print_section("4. Ontology Drift Detection — Loaded Graph")
    print("Checking the Neo4j graph for accumulated drift...\n")

    graph_drift = updater.detect_graph_drift()

    print("  Claim type distribution:")
    for ct, count in graph_drift["claim_type_distribution"].items():
        marker = " ⚠ UNKNOWN" if ct in graph_drift["unknown_claim_types"] else ""
        print(f"    {ct:25} {count:>6,}{marker}")

    print(f"\n  Org type distribution:")
    for ot, count in graph_drift["org_type_distribution"].items():
        marker = " ⚠ UNMAPPED" if ot in graph_drift["unmapped_org_types"] else ""
        label = ot if ot else "(null)"
        print(f"    {label:25} {count:>6,}{marker}")

    print(f"\n  Claims without evidence: {graph_drift['claims_without_evidence']}")
    print(f"  Claims without SUBJECT edge: {graph_drift['claims_without_subject']}")

    # ============================================================
    # 5. SUMMARY
    # ============================================================
    print_section("Summary")
    print(f"  Confidence decay applied: {decay_report['claims_decayed']} decayed, "
          f"{decay_report['claims_archived']} archived")
    print(f"  Ontology drift: {'DETECTED' if drift_report['drift_detected'] else 'NONE'}")
    print(f"  Graph integrity: "
          f"{graph_drift['claims_without_evidence']} claims without evidence, "
          f"{graph_drift['claims_without_subject']} without SUBJECT edge")

    driver.close()
    print("\nDone.")


if __name__ == "__main__":
    main()