"""
init_graph_schema.py

Connects to Neo4j and creates all uniqueness constraints and indexes
for the knowledge graph. Safe to run multiple times — every statement
uses IF NOT EXISTS so re-runs are no-ops.

Usage:
    cd ~/Layer_10_Project2/backend
    source venv/bin/activate
    python scripts/init_graph_schema.py

Requires:
    - Neo4j container running (docker compose up neo4j)
    - NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in .env at project root
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load .env from project root (three levels up from this script)
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not NEO4J_PASSWORD:
    print("ERROR: NEO4J_PASSWORD not found in .env")
    sys.exit(1)


# -------------------------------------------------------------------
# Every Cypher statement to set up the schema
# -------------------------------------------------------------------

CONSTRAINTS = [
    # Uniqueness constraints — also create a backing index automatically
    "CREATE CONSTRAINT person_id_unique IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT org_id_unique IF NOT EXISTS FOR (o:Organization) REQUIRE o.id IS UNIQUE",
    "CREATE CONSTRAINT deal_id_unique IF NOT EXISTS FOR (d:Deal) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT decision_id_unique IF NOT EXISTS FOR (d:Decision) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT claim_id_unique IF NOT EXISTS FOR (c:Claim) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT evidence_id_unique IF NOT EXISTS FOR (e:Evidence) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT message_id_unique IF NOT EXISTS FOR (m:Message) REQUIRE m.message_id IS UNIQUE",
]

INDEXES = [
    # Person lookups — by name and email for entity resolution
    "CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.canonical_name)",

    # Organization lookups
    "CREATE INDEX org_name IF NOT EXISTS FOR (o:Organization) ON (o.canonical_name)",
    "CREATE INDEX org_type IF NOT EXISTS FOR (o:Organization) ON (o.org_type)",

    # Claim filtering — these are the fields your queries will filter on most
    "CREATE INDEX claim_type IF NOT EXISTS FOR (c:Claim) ON (c.type)",
    "CREATE INDEX claim_status IF NOT EXISTS FOR (c:Claim) ON (c.status)",
    "CREATE INDEX claim_valid_from IF NOT EXISTS FOR (c:Claim) ON (c.valid_from)",
    "CREATE INDEX claim_valid_to IF NOT EXISTS FOR (c:Claim) ON (c.valid_to)",
    "CREATE INDEX claim_deleted IF NOT EXISTS FOR (c:Claim) ON (c.is_deleted)",

    # Message lookups — by date for temporal queries
    "CREATE INDEX message_date IF NOT EXISTS FOR (m:Message) ON (m.date)",

    # Soft delete filtering — every query will filter on this
    "CREATE INDEX person_deleted IF NOT EXISTS FOR (p:Person) ON (p.is_deleted)",
    "CREATE INDEX org_deleted IF NOT EXISTS FOR (o:Organization) ON (o.is_deleted)",
    "CREATE INDEX decision_deleted IF NOT EXISTS FOR (d:Decision) ON (d.is_deleted)",
    "CREATE INDEX deal_deleted IF NOT EXISTS FOR (d:Deal) ON (d.is_deleted)",
]


def run():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    # Verify connection works
    try:
        driver.verify_connectivity()
        print(f"Connected to Neo4j at {NEO4J_URI}")
    except Exception as e:
        print(f"ERROR: Cannot connect to Neo4j: {e}")
        print("Is the container running? Try: docker compose up neo4j -d")
        sys.exit(1)

    with driver.session() as session:
        print("\n--- Creating constraints ---")
        for stmt in CONSTRAINTS:
            try:
                session.run(stmt)
                # Extract the constraint name from the statement for display
                name = stmt.split("CONSTRAINT")[1].split("IF")[0].strip()
                print(f"  ✓ {name}")
            except Exception as e:
                print(f"  ✗ FAILED: {e}")

        print("\n--- Creating indexes ---")
        for stmt in INDEXES:
            try:
                session.run(stmt)
                name = stmt.split("INDEX")[1].split("IF")[0].strip()
                print(f"  ✓ {name}")
            except Exception as e:
                print(f"  ✗ FAILED: {e}")

        # Verify by listing what exists
        print("\n--- Verification ---")
        result = session.run("SHOW CONSTRAINTS")
        constraints = list(result)
        print(f"Total constraints: {len(constraints)}")
        for r in constraints:
            print(f"  {r['name']} → {r['labelsOrTypes']} ({r['properties']})")

        result = session.run("SHOW INDEXES")
        indexes = list(result)
        print(f"Total indexes: {len(indexes)}")
        for r in indexes:
            print(f"  {r['name']} → {r['labelsOrTypes']} ({r['properties']})")

    driver.close()
    print("\nDone.")


if __name__ == "__main__":
    run()