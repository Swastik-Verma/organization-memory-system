"""
Day 23 — Batch Graph Loader

Loads all data from Weeks 2-3 into Neo4j.

Usage:
    cd ~/Layer_10_Project2/backend
    source venv/bin/activate
    python scripts/batch_load_graph.py

Requires:
    - Neo4j running at bolt://localhost:7687
    - Schema already applied (python scripts/init_graph_schema.py)
    - Data files in data/processed/:
        entity_resolution_fuzzy.json
        resolution_map.json
        duplicate_ids.json
        extraction_subset.jsonl
        extractions_final.jsonl
        resolved_claims.jsonl

Safe to re-run: all writes use MERGE (idempotent).
"""

import json
import sys
import time
from pathlib import Path

from neo4j import GraphDatabase

# --- Path setup ---
SCRIPT_DIR = Path(__file__).resolve().parent           # backend/scripts/
BACKEND_DIR = SCRIPT_DIR.parent                         # backend/
PROJECT_ROOT = BACKEND_DIR.parent                       # Layer_10_Project2/
DATA_DIR = PROJECT_ROOT / "data" / "processed"

# Add backend to Python path so "from src.graph.loader import ..." works
sys.path.insert(0, str(BACKEND_DIR))

from src.graph.loader import GraphLoader

# --- Neo4j connection ---
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neo4j"  # overridden from .env below

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


def verify_data_files():
    """Check all required files exist before starting."""
    required = [
        "entity_resolution_fuzzy.json",
        "resolution_map.json",
        "duplicate_ids.json",
        "extraction_subset.jsonl",
        "extractions_final.jsonl",
        "resolved_claims.jsonl",
    ]
    missing = [f for f in required if not (DATA_DIR / f).exists()]
    if missing:
        print("ERROR: Missing required data files:")
        for f in missing:
            print(f"  {DATA_DIR / f}")
        print("\nThese files are produced by the Week 2-3 pipeline.")
        sys.exit(1)
    print("All required data files found.")


def print_final_stats(driver):
    """Query Neo4j for actual node/edge counts after loading."""
    with driver.session() as session:
        print("\n=== Graph Contents ===")

        # Node counts by label
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
            print(f"  {record['label']:15} {record['cnt']:>8,}")
            total_nodes += record['cnt']
        print(f"  {'TOTAL':15} {total_nodes:>8,}")

        # Edge counts by type
        print()
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) AS rel_type, count(r) AS cnt
            ORDER BY cnt DESC
        """)
        total_edges = 0
        for record in result:
            print(f"  {record['rel_type']:20} {record['cnt']:>8,}")
            total_edges += record['cnt']
        print(f"  {'TOTAL':20} {total_edges:>8,}")

        # Quick sanity checks
        print("\n=== Sanity Checks ===")

        # Claims with no SUBJECT edge (should be 0 ideally)
        result = session.run("""
            MATCH (c:Claim)
            WHERE NOT (c)-[:SUBJECT]->()
            RETURN count(c) AS orphan_claims
        """)
        orphans = result.single()["orphan_claims"]
        print(f"  Claims without SUBJECT edge: {orphans}")

        # Current claims (the "live" knowledge)
        result = session.run("""
            MATCH (c:Claim {status: 'current', is_deleted: false})
            RETURN count(c) AS current_claims
        """)
        current = result.single()["current_claims"]
        print(f"  Current (live) claims: {current:,}")

        # Superseded claims
        result = session.run("""
            MATCH (c:Claim {status: 'superseded'})
            RETURN count(c) AS superseded
        """)
        superseded = result.single()["superseded"]
        print(f"  Superseded claims: {superseded}")

        # Claims in review
        result = session.run("""
            MATCH (c:Claim {status: 'review'})
            RETURN count(c) AS review
        """)
        review = result.single()["review"]
        print(f"  Claims needing review: {review}")


def main():
    load_env()

    print("=" * 60)
    print("  Layer 10 — Graph Loader (Day 23)")
    print("=" * 60)
    print(f"\nData directory: {DATA_DIR}")
    print(f"Neo4j: {NEO4J_URI}")
    print()

    verify_data_files()

    print(f"\nConnecting to Neo4j at {NEO4J_URI}...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        driver.verify_connectivity()
        print("Connected.\n")
    except Exception as e:
        print(f"ERROR: Cannot connect to Neo4j: {e}")
        print("Is Neo4j running? Try: cd ~/Layer_10_Project2 && docker compose up neo4j -d")
        sys.exit(1)

    # --- Load ---
    start_time = time.time()
    loader = GraphLoader(driver, DATA_DIR)
    stats = loader.load_all()
    elapsed = time.time() - start_time

    # --- Report ---
    print(f"\n{'=' * 60}")
    print(f"  Loading complete in {elapsed:.1f} seconds")
    print(f"{'=' * 60}")
    print("\nLoader stats:")
    for key, value in stats.items():
        print(f"  {key:25} {value:>8,}")

    print_final_stats(driver)

    driver.close()
    print("\nDone. You can now query the graph in Neo4j Browser at http://localhost:7474")


if __name__ == "__main__":
    main()