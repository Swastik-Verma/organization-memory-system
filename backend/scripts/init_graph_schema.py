"""
Day 22 — Neo4j Schema Initialization (Revised)

Replaces the Day 5 version. Aligned with Week 3 output:
- Person IDs: person:{normalized-name}:{email-slug}
- Claim IDs: fact-level (one claim per deduplicated fact)
- New fields: supersedes, superseded_by, conflicts_with, mention_count
- New edges: SUPERSEDES, CONFLICTS_WITH
- Deletion fields on all node types

Usage:
    cd ~/Layer_10_Project2/backend
    source venv/bin/activate
    python scripts/init_graph_schema.py [--drop-existing]

Requires: Neo4j running at bolt://localhost:7687
"""

import argparse
import sys
from pathlib import Path

from neo4j import GraphDatabase

# --- Connection config ---
# Reads from .env at project root if available, otherwise defaults
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neo4j"  # default; overridden from .env below

def load_env():
    """Load NEO4J_* vars from .env file."""
    global NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
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


# ============================================================
# SCHEMA DEFINITION
# ============================================================

# --- Uniqueness constraints ---
# One per node type. Prevents duplicate nodes on re-run (idempotent MERGE).
# Each constraint also implicitly creates a backing index.
CONSTRAINTS = [
    # (constraint_name, label, property)
    ("person_id_unique",    "Person",       "id"),
    ("org_id_unique",       "Organization", "id"),
    ("deal_id_unique",      "Deal",         "id"),
    ("decision_id_unique",  "Decision",     "id"),
    ("claim_id_unique",     "Claim",        "id"),
    ("evidence_id_unique",  "Evidence",     "id"),
    ("message_id_unique",   "Message",      "message_id"),
]

# --- Indexes ---
# Created on properties we'll query/filter/sort on frequently.
# Constraint-backing indexes already cover the id fields.
INDEXES = [
    # (index_name, label, property_or_properties, index_type)
    # index_type: "single" for single-property, "text" for full-text search

    # Person lookups
    ("idx_person_canonical_name",  "Person",       "canonical_name",  "single"),
    ("idx_person_is_deleted",      "Person",       "is_deleted",      "single"),

    # Organization lookups
    ("idx_org_canonical_name",     "Organization", "canonical_name",  "single"),
    ("idx_org_type",               "Organization", "org_type",        "single"),
    ("idx_org_is_deleted",         "Organization", "is_deleted",      "single"),

    # Message lookups
    ("idx_message_date",           "Message",      "date",            "single"),
    ("idx_message_from_addr",      "Message",      "from_addr",       "single"),
    ("idx_message_x_origin",       "Message",      "x_origin",        "single"),
    ("idx_message_is_deleted",     "Message",      "is_deleted",      "single"),

    # Claim lookups (the workhorse — most queries touch claims)
    ("idx_claim_type",             "Claim",        "claim_type",      "single"),
    ("idx_claim_status",           "Claim",        "status",          "single"),
    ("idx_claim_valid_from",       "Claim",        "valid_from",      "single"),
    ("idx_claim_valid_to",         "Claim",        "valid_to",        "single"),
    ("idx_claim_is_deleted",       "Claim",        "is_deleted",      "single"),
    ("idx_claim_confidence",       "Claim",        "confidence",      "single"),
    ("idx_claim_superseded_by",    "Claim",        "superseded_by",   "single"),

    # Evidence lookups
    ("idx_evidence_verified",      "Evidence",     "evidence_verified", "single"),
    ("idx_evidence_is_deleted",    "Evidence",     "is_deleted",      "single"),

    # Deal & Decision
    ("idx_deal_is_deleted",        "Deal",         "is_deleted",      "single"),
    ("idx_decision_is_deleted",    "Decision",     "is_deleted",      "single"),
]


# ============================================================
# SCHEMA OPERATIONS
# ============================================================

def drop_all_constraints_and_indexes(session):
    """Drop all user-created constraints and indexes. Leaves system indexes intact."""
    # Drop constraints first (they depend on their backing indexes)
    result = session.run("SHOW CONSTRAINTS YIELD name RETURN name")
    constraints = [record["name"] for record in result]
    for name in constraints:
        session.run(f"DROP CONSTRAINT {name} IF EXISTS")
        print(f"  Dropped constraint: {name}")

    # Drop non-system indexes
    result = session.run(
        "SHOW INDEXES YIELD name, type "
        "WHERE type <> 'LOOKUP' "  # LOOKUP indexes are system-managed
        "RETURN name"
    )
    indexes = [record["name"] for record in result]
    for name in indexes:
        session.run(f"DROP INDEX {name} IF EXISTS")
        print(f"  Dropped index: {name}")


def delete_all_data(session):
    """Delete all nodes and relationships in batches to stay within memory limits."""
    total_deleted = 0
    while True:
        result = session.run("""
            MATCH (n)
            WITH n LIMIT 1000
            DETACH DELETE n
            RETURN count(n) AS deleted
        """)
        deleted = result.single()["deleted"]
        total_deleted += deleted
        if deleted == 0:
            break
    print(f"  Deleted {total_deleted} nodes (and all their relationships)")


def create_constraints(session):
    """Create uniqueness constraints. Each also creates a backing index."""
    for name, label, prop in CONSTRAINTS:
        cypher = (
            f"CREATE CONSTRAINT {name} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
        )
        session.run(cypher)
        print(f"  Created constraint: {name} ({label}.{prop})")


def create_indexes(session):
    """Create range indexes for query performance."""
    for name, label, prop, idx_type in INDEXES:
        if idx_type == "single":
            cypher = (
                f"CREATE INDEX {name} IF NOT EXISTS "
                f"FOR (n:{label}) ON (n.{prop})"
            )
        # Could add composite or text index types here if needed
        session.run(cypher)
        print(f"  Created index: {name} ({label}.{prop})")


def verify_schema(session):
    """Print current constraints and indexes for verification."""
    print("\n--- Constraints ---")
    result = session.run("SHOW CONSTRAINTS YIELD name, labelsOrTypes, properties")
    constraint_count = 0
    for record in result:
        print(f"  {record['name']}: {record['labelsOrTypes']} on {record['properties']}")
        constraint_count += 1
    print(f"  Total: {constraint_count}")

    print("\n--- Indexes (excluding system LOOKUP) ---")
    result = session.run(
        "SHOW INDEXES YIELD name, labelsOrTypes, properties, type "
        "WHERE type <> 'LOOKUP' "
        "RETURN name, labelsOrTypes, properties, type"
    )
    index_count = 0
    for record in result:
        print(f"  {record['name']}: {record['labelsOrTypes']} on {record['properties']} ({record['type']})")
        index_count += 1
    print(f"  Total: {index_count} (includes {constraint_count} constraint-backing)")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Initialize/reset Neo4j schema for Layer 10")
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop all existing constraints, indexes, and data before creating new schema"
    )
    args = parser.parse_args()

    load_env()

    print(f"Connecting to Neo4j at {NEO4J_URI}...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        driver.verify_connectivity()
        print("Connected.\n")
    except Exception as e:
        print(f"ERROR: Cannot connect to Neo4j: {e}")
        print("Is Neo4j running? Try: cd ~/Layer_10_Project2 && docker compose up neo4j -d")
        sys.exit(1)

    with driver.session() as session:
        if args.drop_existing:
            print("=== Dropping existing schema and data ===")
            drop_all_constraints_and_indexes(session)
            delete_all_data(session)
            print()

        print("=== Creating constraints ===")
        create_constraints(session)
        print()

        print("=== Creating indexes ===")
        create_indexes(session)

        print()
        print("=== Verifying schema ===")
        verify_schema(session)

    driver.close()
    print("\nDone.")


if __name__ == "__main__":
    main()