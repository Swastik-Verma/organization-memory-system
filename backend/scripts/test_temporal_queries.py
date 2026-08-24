"""
Day 24 — Test the Temporal Query Engine

Runs all query types against the loaded graph and prints results.

Usage:
    cd ~/Layer_10_Project2/backend
    source venv/bin/activate
    python scripts/test_temporal_queries.py
"""

import json
import sys
from pathlib import Path

from neo4j import GraphDatabase

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

sys.path.insert(0, str(BACKEND_DIR))

from src.graph.temporal_queries import TemporalQueryEngine

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
                if key == "NEO4J_URI":
                    NEO4J_URI = value
                elif key == "NEO4J_USER":
                    NEO4J_USER = value
                elif key == "NEO4J_PASSWORD":
                    NEO4J_PASSWORD = value


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_results(results: list[dict], max_rows: int = 10):
    if not results:
        print("  (no results)")
        return
    for i, row in enumerate(results[:max_rows]):
        print(f"\n  [{i+1}]")
        for key, value in row.items():
            if isinstance(value, list) and len(value) > 3:
                value = f"{value[:3]} ... ({len(value)} total)"
            print(f"    {key}: {value}")
    if len(results) > max_rows:
        print(f"\n  ... and {len(results) - max_rows} more")


def main():
    load_env()

    print("Connecting to Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print("Connected.\n")

    engine = TemporalQueryEngine(driver)

    # ---- Test 1: Find entity ----
    print_section("Test 1: Find entity by name — 'Kean'")
    results = engine.find_entity("Kean")
    print_results(results, max_rows=5)

    # Pick the top result for subsequent queries
    if not results:
        print("ERROR: No entity found for 'Kean'. Is the graph loaded?")
        driver.close()
        return

    entity_id = results[0]["id"]
    entity_name = results[0]["canonical_name"]
    print(f"\n  Using: {entity_name} ({entity_id})")

    # ---- Test 2: Entity profile ----
    print_section(f"Test 2: Entity profile — {entity_name}")
    profile = engine.get_entity_profile(entity_id)
    if profile:
        for key, value in profile.items():
            print(f"  {key}: {value}")

    # ---- Test 3: Current state ----
    print_section(f"Test 3: Current state — {entity_name}")
    current = engine.get_current_state(entity_id)
    print_results(current)

    # ---- Test 4: Current state filtered by type ----
    print_section(f"Test 4: Current reports_to — {entity_name}")
    reports = engine.get_current_state(entity_id, claim_type="reports_to")
    print_results(reports)

    # ---- Test 5: Historical state at a specific date ----
    print_section(f"Test 5: State at 2001-01-15 — {entity_name}")
    past = engine.get_state_at(entity_id, "2001-01-15")
    print_results(past)

    # ---- Test 6: Full history ----
    print_section(f"Test 6: Full history — {entity_name}")
    history = engine.get_full_history(entity_id)
    print_results(history)

    # ---- Test 7: Full history filtered by reports_to ----
    print_section(f"Test 7: Reporting history — {entity_name}")
    reporting = engine.get_full_history(entity_id, claim_type="reports_to")
    print_results(reporting)

    # ---- Test 8: Evidence trail for a claim ----
    if current:
        claim_id = current[0]["claim_id"]
        print_section(f"Test 8: Evidence for claim — {claim_id}")
        evidence = engine.get_evidence_for_claim(claim_id)
        print_results(evidence)

        # ---- Test 9: Full email for first evidence ----
        if evidence:
            msg_id = evidence[0].get("message_id")
            if msg_id:
                print_section(f"Test 9: Full email — {msg_id[:50]}...")
                email = engine.get_full_email(msg_id)
                if email:
                    print(f"  Subject: {email.get('subject')}")
                    print(f"  From: {email.get('from_addr')}")
                    print(f"  Date: {email.get('date')}")
                    body = email.get('body', '')
                    print(f"  Body: {body[:200]}..." if len(body) > 200 else f"  Body: {body}")

    # ---- Test 10: Relationships involving (both directions) ----
    print_section(f"Test 10: All relationships involving — {entity_name}")
    involving = engine.get_relationships_involving(entity_id)
    print_results(involving)

    # ---- Test 11: Decisions by this person ----
    print_section(f"Test 11: Decisions made by — {entity_name}")
    decisions = engine.get_decisions_by(entity_id)
    print_results(decisions, max_rows=5)

    # ---- Test 12: Deals involving this person ----
    print_section(f"Test 12: Deals involving — {entity_name}")
    deals = engine.get_deals_involving(entity_id)
    print_results(deals, max_rows=5)

    # ---- Test 13: Conflicts ----
    print_section("Test 13: All unresolved conflicts")
    conflicts = engine.get_conflicts()
    print_results(conflicts)

    # ---- Test 14: Graph statistics ----
    print_section("Test 14: Graph statistics")
    stats = engine.get_graph_stats()
    for metric, value in sorted(stats.items()):
        print(f"  {metric:25} {value:>8,}")

    # ---- Test 15: Another person for comparison ----
    print_section("Test 15: Find and query 'Sally Beck'")
    beck_results = engine.find_entity("Sally Beck")
    if beck_results:
        beck_id = beck_results[0]["id"]
        beck_name = beck_results[0]["canonical_name"]
        print(f"  Found: {beck_name}")

        reporting = engine.get_full_history(beck_id, claim_type="reports_to")
        print(f"\n  Reporting history for {beck_name}:")
        for r in reporting:
            status_marker = "→" if r["status"] == "current" else "×"
            print(f"    {status_marker} reports_to {r['object_name']}: "
                  f"{r['valid_from']} to {r['valid_to'] or 'present'} "
                  f"({r['status']}, {r['evidence_count']} evidence)")

    driver.close()
    print("\n\nDone.")


if __name__ == "__main__":
    main()