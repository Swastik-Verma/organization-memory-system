"""
Build the Qdrant vector index from Neo4j evidence nodes.

Reads all active (non-deleted) Evidence nodes from Neo4j,
enriches them with claim metadata, embeds the quotes,
and upserts into Qdrant.

Usage:
    python scripts/build_vector_index.py
    python scripts/build_vector_index.py --recreate   # drop and rebuild
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# -- path setup (same pattern as all your scripts) --
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root / "backend"))

from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv(_project_root / ".env")

from src.retrieval.qdrant_index import QdrantIndex

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")


def fetch_evidence_from_neo4j(driver) -> list[dict]:
    """
    Fetch all active evidence with claim metadata from Neo4j.

    Query joins Evidence → Claim (via SUPPORTED_BY) to get
    claim_type, subject_id, object_id, confidence, access_level, valid_from.
    Also joins Evidence → Message (via FROM_MESSAGE) to get message_id.
    """
    query = """
    MATCH (e:Evidence)
    WHERE e.is_deleted = false
    OPTIONAL MATCH (c:Claim)-[:SUPPORTED_BY]->(e)
    OPTIONAL MATCH (e)-[:FROM_MESSAGE]->(m:Message)
    RETURN
        e.evidence_id AS evidence_id,
        e.quote AS quote,
        e.evidence_verified AS evidence_verified,
        c.id AS claim_id,
        c.claim_type AS claim_type,
        c.confidence AS confidence,
        c.access_level AS access_level,
        c.valid_from AS valid_from,
        c.is_deleted AS claim_is_deleted,
        c.subject_id AS subject_id,
        c.object_id AS object_id,
        m.message_id AS message_id,
        e.is_deleted AS is_deleted,
        c.valid_to AS valid_to,
        c.status AS status,
        c.mention_count AS mention_count,
        c.subject_name AS subject_name,
        c.object_name AS object_name
    """

    records = []
    with driver.session() as session:
        result = session.run(query)
        for row in result:
            # Subject could be Person or Org
            subject_id = row["subject_id"] or ""
            object_id = row["object_id"] or ""

            # Format valid_from as ISO string
            valid_from_raw = row["valid_from"]
            if valid_from_raw is not None:
                if hasattr(valid_from_raw, "iso_format"):
                    valid_from = valid_from_raw.iso_format()
                else:
                    valid_from = str(valid_from_raw)
            else:
                valid_from = None

            # Format valid_to as ISO string
            valid_to_raw = row["valid_to"]
            if valid_to_raw is not None:
                if hasattr(valid_to_raw, "iso_format"):
                    valid_to = valid_to_raw.iso_format()
                else:
                    valid_to = str(valid_to_raw)
            else:
                valid_to = None

            records.append({
                "evidence_id": row["evidence_id"],
                "quote": row["quote"] or "",
                "claim_id": row["claim_id"] or "",
                "claim_type": row["claim_type"] or "",
                "subject_id": subject_id,
                "object_id": object_id,
                "confidence": row["confidence"] or 0.0,
                "access_level": row["access_level"] or 1,
                "valid_from": valid_from,
                "message_id": row["message_id"] or "",
                "is_deleted": row["is_deleted"] or False,
                "valid_to": valid_to,
                "status": row["status"] or "",
                "mention_count": row["mention_count"] or 0,
                "subject_name": row["subject_name"] or "",
                "object_name": row["object_name"] or "",
            })

    return records


def main():
    parser = argparse.ArgumentParser(description="Build Qdrant vector index")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop existing collection and rebuild from scratch",
    )
    args = parser.parse_args()

    # Connect to Neo4j
    logger.info("Connecting to Neo4j at %s", NEO4J_URI)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()

    # Fetch evidence
    logger.info("Fetching evidence from Neo4j...")
    t0 = time.time()
    records = fetch_evidence_from_neo4j(driver)
    fetch_time = time.time() - t0
    logger.info("Fetched %d evidence records in %.1fs", len(records), fetch_time)

    driver.close()

    # Filter: skip evidence whose parent claim is also deleted
    active_records = [r for r in records if not r["is_deleted"]]
    active_records = [r for r in active_records if r.get("evidence_id")]
    skipped = len(records) - len(active_records)
    if skipped:
        logger.warning("Skipped %d records with null evidence_id", skipped)
    logger.info("Active (non-deleted) evidence: %d", len(active_records))

    # Build vector index
    logger.info("Connecting to Qdrant at %s", QDRANT_URL)
    index = QdrantIndex(qdrant_url=QDRANT_URL)
    index.create_collection(recreate=args.recreate)

    logger.info("Embedding and upserting %d evidence records...", len(active_records))
    t0 = time.time()
    count = index.upsert_evidence(active_records)
    embed_time = time.time() - t0
    logger.info("Upserted %d vectors in %.1fs", count, embed_time)

    # Print summary
    info = index.get_collection_info()
    logger.info("--- Collection Summary ---")
    logger.info("  Name:          %s", info["name"])
    logger.info("  Points count:  %d", info["points_count"])
    logger.info("  Status:        %s", info["status"])

    # Quick sanity search
    logger.info("--- Sanity Check: searching 'California energy trading' ---")
    results = index.semantic_search("California energy trading", top_k=3)
    for i, r in enumerate(results):
        logger.info(
            "  [%d] score=%.4f  claim_type=%s  quote=%s",
            i + 1,
            r["score"],
            r["claim_type"],
            r["quote"][:80] + "..." if len(r["quote"]) > 80 else r["quote"],
        )


if __name__ == "__main__":
    main()