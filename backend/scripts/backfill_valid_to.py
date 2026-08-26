"""
Backfill valid_to into Neo4j Claim nodes from resolved_claims.jsonl.

The deduplication pipeline computed valid_to for superseded claims
but the graph loader never wrote it to Neo4j. This script reads
the JSONL and updates each Claim node:
  - If valid_to exists in the JSONL → SET c.valid_to = value
  - If valid_to is null/missing     → SET c.valid_to = null

Usage:
    python scripts/backfill_valid_to.py
    python scripts/backfill_valid_to.py --dry-run   # preview without writing
"""

import argparse
import json
import logging
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root / "backend"))

from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv(_project_root / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

RESOLVED_CLAIMS_PATH = _project_root / "data" / "processed" / "resolved_claims.jsonl"

BATCH_SIZE = 500


def load_valid_to_from_jsonl(path: Path) -> list[dict]:
    """
    Read resolved_claims.jsonl and extract claim_id + valid_to for every claim.

    Returns list of {"claim_id": "claim:abc123", "valid_to": "2001-03-15" or None}
    """
    records = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            claim = json.loads(line)
            records.append({
                "claim_id": claim["claim_id"],
                "valid_to": claim.get("valid_to"),  # None if missing
            })
    return records


def backfill(driver, records: list[dict], dry_run: bool = False) -> dict:
    """
    Update Claim nodes in Neo4j with valid_to values.

    For every claim:
      - valid_to is a date string → SET c.valid_to = value
      - valid_to is None          → SET c.valid_to = null (explicit)
    """
    has_value = [r for r in records if r["valid_to"] is not None]
    null_value = [r for r in records if r["valid_to"] is None]

    logger.info(
        "Claims with valid_to: %d,  Claims without (will set null): %d",
        len(has_value), len(null_value),
    )

    if dry_run:
        logger.info("DRY RUN — no changes written to Neo4j")
        # Show a few examples
        for r in has_value[:5]:
            logger.info("  Would set %s → valid_to = %s", r["claim_id"], r["valid_to"])
        if len(has_value) > 5:
            logger.info("  ... and %d more", len(has_value) - 5)
        return {"updated_with_value": 0, "updated_with_null": 0}

    updated_with_value = 0
    updated_with_null = 0

    # Batch update claims that HAVE valid_to
    with driver.session() as session:
        for i in range(0, len(has_value), BATCH_SIZE):
            batch = has_value[i : i + BATCH_SIZE]
            params = [{"claim_id": r["claim_id"], "valid_to": r["valid_to"]} for r in batch]

            result = session.run(
                """
                UNWIND $params AS p
                MATCH (c:Claim {id: p.claim_id})
                SET c.valid_to = p.valid_to
                RETURN count(c) AS updated
                """,
                params=params,
            )
            count = result.single()["updated"]
            updated_with_value += count
            logger.info(
                "  Batch %d: set valid_to on %d claims (%d / %d)",
                i // BATCH_SIZE + 1, count, min(i + BATCH_SIZE, len(has_value)), len(has_value),
            )

    # Batch update claims that have NULL valid_to (explicit null)
    with driver.session() as session:
        for i in range(0, len(null_value), BATCH_SIZE):
            batch = null_value[i : i + BATCH_SIZE]
            ids = [r["claim_id"] for r in batch]

            result = session.run(
                """
                UNWIND $ids AS cid
                MATCH (c:Claim {id: cid})
                SET c.valid_to = null
                RETURN count(c) AS updated
                """,
                ids=ids,
            )
            count = result.single()["updated"]
            updated_with_null += count

    return {"updated_with_value": updated_with_value, "updated_with_null": updated_with_null}


def main():
    parser = argparse.ArgumentParser(description="Backfill valid_to into Neo4j Claim nodes")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be updated without writing to Neo4j",
    )
    args = parser.parse_args()

    # Load from JSONL
    logger.info("Reading %s", RESOLVED_CLAIMS_PATH)
    records = load_valid_to_from_jsonl(RESOLVED_CLAIMS_PATH)
    logger.info("Loaded %d claims from JSONL", len(records))

    # Connect to Neo4j
    logger.info("Connecting to Neo4j at %s", NEO4J_URI)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()

    # Run backfill
    stats = backfill(driver, records, dry_run=args.dry_run)

    driver.close()

    # Summary
    logger.info("--- Backfill Complete ---")
    logger.info("  Claims with valid_to set:  %d", stats["updated_with_value"])
    logger.info("  Claims with valid_to null: %d", stats["updated_with_null"])

    # Verification hint
    if not args.dry_run:
        logger.info("Verify with:  MATCH (c:Claim) WHERE c.valid_to IS NOT NULL RETURN count(c)")


if __name__ == "__main__":
    main()