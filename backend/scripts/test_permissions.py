"""
Day 26 — Permission Layer Runner

Demonstrates:
1. Assigning access levels to graph content
2. Querying with different user clearance levels
3. Proving that restricted content is invisible to low-clearance users

Usage:
    cd ~/Layer_10_Project2/backend
    source venv/bin/activate
    python scripts/test_permissions.py

    To undo all access level assignments:
    python scripts/test_permissions.py --clear
"""

import argparse
import sys
from pathlib import Path

from neo4j import GraphDatabase

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

sys.path.insert(0, str(BACKEND_DIR))

from src.graph.permissions import (
    PermissionManager, UserContext,
    PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED,
    ACCESS_LEVEL_NAMES,
)
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
                if key == "NEO4J_URI": NEO4J_URI = value
                elif key == "NEO4J_USER": NEO4J_USER = value
                elif key == "NEO4J_PASSWORD": NEO4J_PASSWORD = value


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true",
                        help="Clear all access level assignments and exit")
    args = parser.parse_args()

    load_env()

    print("Connecting to Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print("Connected.\n")

    pm = PermissionManager(driver)
    engine = TemporalQueryEngine(driver)

    if args.clear:
        print("Clearing all access level assignments...")
        counts = pm.clear_access_levels()
        for label, count in counts.items():
            print(f"  {label}: {count} cleared")
        driver.close()
        print("\nDone. All access levels removed.")
        return

    # ============================================================
    # 1. ASSIGN ACCESS LEVELS
    # ============================================================
    print_section("1. Assigning access levels to graph content")
    report = pm.assign_access_levels()

    print(f"  Messages classified: {report['messages_classified']:,}")
    print(f"  Evidence classified: {report['evidence_classified']:,}")
    print(f"  Claims classified:   {report['claims_classified']:,}")
    print(f"  Decisions classified: {report['decisions_classified']:,}")

    # ============================================================
    # 2. ACCESS LEVEL DISTRIBUTION
    # ============================================================
    print_section("2. Access level distribution")
    stats = pm.get_access_level_stats()
    for label, dist in stats.items():
        print(f"\n  {label}:")
        for level_name, count in dist.items():
            print(f"    {level_name:15} {count:>8,}")

    # ============================================================
    # 3. FILTERED QUERIES — COMPARE CLEARANCE LEVELS
    # ============================================================
    print_section("3. Permission-filtered queries — comparing clearance levels")

    # Find a well-known entity
    entities = engine.find_entity("Kean")
    if not entities:
        print("  No entity found. Is the graph loaded?")
        driver.close()
        return

    entity_id = entities[0]["id"]
    entity_name = entities[0]["canonical_name"]
    print(f"\n  Querying current state for: {entity_name}")

    # Create users at different clearance levels
    users = [
        UserContext(user_id="intern", clearance_level=PUBLIC),
        UserContext(user_id="employee", clearance_level=INTERNAL),
        UserContext(user_id="manager", clearance_level=CONFIDENTIAL),
        UserContext(user_id="executive", clearance_level=RESTRICTED),
    ]

    for user in users:
        results = pm.filtered_current_state(engine, entity_id, user)
        level_name = ACCESS_LEVEL_NAMES[user.clearance_level]
        print(f"\n  {user.user_id} (clearance={level_name}): "
              f"{len(results)} claims visible")

        # Show breakdown by access level
        if results:
            level_counts = {}
            for r in results:
                al = r.get("access_level", 1)
                level_counts[al] = level_counts.get(al, 0) + 1
            for level, count in sorted(level_counts.items()):
                print(f"    Level {level} ({ACCESS_LEVEL_NAMES.get(level, '?')}): {count}")

    # ============================================================
    # 4. EVIDENCE FILTERING
    # ============================================================
    print_section("4. Evidence filtering by clearance")

    # Get a claim that has evidence
    all_claims = pm.filtered_current_state(engine, entity_id,
                                            UserContext("admin", RESTRICTED))
    if all_claims:
        claim_id = all_claims[0]["claim_id"]
        print(f"  Claim: {all_claims[0]['description']}")
        print()

        for user in users:
            evidence = pm.filtered_evidence(claim_id, user)
            level_name = ACCESS_LEVEL_NAMES[user.clearance_level]
            print(f"  {user.user_id} (clearance={level_name}): "
                  f"{len(evidence)} evidence items visible")

    # ============================================================
    # 5. PROOF: RESTRICTED CONTENT IS INVISIBLE
    # ============================================================
    print_section("5. Proof: restricted content is invisible to low-clearance users")

    # Count claims at each level
    with driver.session() as session:
        result = session.run("""
            MATCH (c:Claim)
            WHERE c.is_deleted = false AND c.access_level = 4
            RETURN count(c) AS restricted_count
        """)
        restricted_count = result.single()["restricted_count"]

    if restricted_count > 0:
        # Intern should NOT see these
        intern = UserContext("intern", PUBLIC)
        exec_user = UserContext("exec", RESTRICTED)

        intern_results = pm.filtered_current_state(engine, entity_id, intern)
        exec_results = pm.filtered_current_state(engine, entity_id, exec_user)

        print(f"  Restricted claims in graph: {restricted_count}")
        print(f"  Intern sees: {len(intern_results)} claims")
        print(f"  Executive sees: {len(exec_results)} claims")

        if len(exec_results) > len(intern_results):
            print(f"  PROOF: Executive sees {len(exec_results) - len(intern_results)} "
                  f"more claims than intern")
        else:
            print(f"  (No restricted claims for this entity — "
                  f"try querying an executive like Kenneth Lay)")
    else:
        print("  No RESTRICTED content found in graph.")
        print("  (This is expected if no emails matched restricted keywords)")

    driver.close()
    print("\n\nDone.")


if __name__ == "__main__":
    main()