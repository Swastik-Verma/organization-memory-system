"""
Batch claim deduplication runner (Day 18).

Loads extractions, resolves names via the resolution map,
deduplicates relationship claims, and detects conflicts.

Reads:
  - data/processed/extractions_final.jsonl     (relationships)
  - data/processed/extraction_subset.jsonl     (email dates)
  - data/processed/resolution_map.json         (name → canonical_id)
  - data/processed/entity_resolution_fuzzy.json (canonical entities)
  - data/processed/duplicate_ids.json          (emails to skip)

Outputs:
  - data/processed/deduplicated_claims.jsonl   (one claim per line)
  - data/processed/claim_conflicts.json        (detected conflicts)
  - data/processed/claim_dedup_report.json     (statistics)

Usage:
    cd ~/Layer_10_Project2/backend
    source venv/bin/activate
    python scripts/batch_claim_dedup.py
"""

import json
import logging
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

sys.path.insert(0, str(BACKEND_DIR))

from src.deduplication.claim_dedup import deduplicate_claims

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            records.append(json.loads(line))
    return records


def load_json(path: Path) -> dict | list:
    with open(path) as f:
        return json.load(f)


def main():
    data_dir = PROJECT_ROOT / "data" / "processed"

    # --- Load inputs ---

    extractions_path = data_dir / "extractions_final.jsonl"
    subset_path = data_dir / "extraction_subset.jsonl"
    resolution_map_path = data_dir / "resolution_map.json"
    dup_ids_path = data_dir / "duplicate_ids.json"

    # Try fuzzy resolution first (Day 17), fall back to exact (Day 16)
    fuzzy_path = data_dir / "entity_resolution_fuzzy.json"
    exact_path = data_dir / "entity_resolution_exact.json"

    for required in [extractions_path, subset_path, resolution_map_path]:
        if not required.exists():
            logger.error("Required file not found: %s", required)
            sys.exit(1)

    logger.info("Loading extractions…")
    extractions = load_jsonl(extractions_path)

    logger.info("Loading email dates from extraction subset…")
    subset = load_jsonl(subset_path)
    email_dates = {}
    for email in subset:
        msg_id = email.get("message_id")
        date = email.get("date")
        if msg_id:
            # Date might be a full ISO datetime — extract just the date part
            if date and "T" in str(date):
                date = str(date).split("T")[0]
            email_dates[msg_id] = date

    logger.info("Loading resolution map…")
    resolution_map = load_json(resolution_map_path)

    logger.info("Loading canonical entities…")
    if fuzzy_path.exists():
        fuzzy_data = load_json(fuzzy_path)
        canonical_entities = fuzzy_data.get("canonical_entities", {})
        logger.info("Using fuzzy resolution entities (Day 17)")
    elif exact_path.exists():
        exact_data = load_json(exact_path)
        canonical_entities = exact_data.get("canonical_entities", {})
        logger.info("Using exact resolution entities (Day 16)")
    else:
        logger.warning("No entity resolution file found — using empty entities")
        canonical_entities = {}

    duplicate_ids = set()
    if dup_ids_path.exists():
        duplicate_ids = set(load_json(dup_ids_path))
        logger.info("Loaded %d duplicate IDs to skip", len(duplicate_ids))

    # --- Run dedup ---

    logger.info("Running claim deduplication…")
    claims, conflicts = deduplicate_claims(
        extractions=extractions,
        email_dates=email_dates,
        resolution_map=resolution_map,
        canonical_entities=canonical_entities,
        duplicate_ids=duplicate_ids,
    )

    # --- Statistics ---

    total_evidence = sum(c.mention_count for c in claims)
    type_counts = Counter(c.claim_type for c in claims)
    multi_evidence = [c for c in claims if c.mention_count > 1]
    single_evidence = [c for c in claims if c.mention_count == 1]
    max_evidence = max((c.mention_count for c in claims), default=0)
    top_claim = next((c for c in claims if c.mention_count == max_evidence), None)

    conflict_type_counts = Counter(c.claim_type for c in conflicts)

    stats = {
        "total_input_relationships": total_evidence,
        "deduplicated_claims": len(claims),
        "compression_ratio": round(total_evidence / len(claims), 2) if claims else 0,
        "claims_with_multiple_evidence": len(multi_evidence),
        "claims_with_single_evidence": len(single_evidence),
        "max_evidence_per_claim": max_evidence,
        "top_claim": {
            "description": top_claim.description if top_claim else None,
            "mention_count": max_evidence,
        },
        "claims_by_type": dict(type_counts),
        "total_conflicts": len(conflicts),
        "conflicts_by_type": dict(conflict_type_counts),
        "unresolved_person_references": sum(
            1 for c in claims
            if ":unresolved" in c.subject_id or ":unresolved" in c.object_id
        ),
    }

    print("\n" + "=" * 65)
    print("CLAIM DEDUPLICATION RESULTS")
    print("=" * 65)
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print("=" * 65)

    # Show top merged claims
    print(f"\nTop 10 most-supported claims:")
    for c in claims[:10]:
        print(f"  [{c.mention_count}x] {c.description}")
        print(f"       confidence: {c.confidence}, valid_from: {c.valid_from}")

    # Show conflicts
    if conflicts:
        print(f"\nTop 10 conflicts (of {len(conflicts)}):")
        for conf in conflicts[:10]:
            objects = [cl["object_name"] for cl in conf.claims]
            print(f"  {conf.subject_name} {conf.claim_type} → {objects}")
    else:
        print("\nNo conflicts detected.")

    # --- Save outputs ---

    # Deduplicated claims
    claims_path = data_dir / "deduplicated_claims.jsonl"
    with open(claims_path, "w") as f:
        for claim in claims:
            f.write(json.dumps(claim.to_dict()) + "\n")
    logger.info("Saved %d deduplicated claims to %s", len(claims), claims_path)

    # Conflicts
    conflicts_path = data_dir / "claim_conflicts.json"
    with open(conflicts_path, "w") as f:
        json.dump({
            "total_conflicts": len(conflicts),
            "conflicts": [c.to_dict() for c in conflicts],
        }, f, indent=2)
    logger.info("Saved %d conflicts to %s", len(conflicts), conflicts_path)

    # Report
    report_path = data_dir / "claim_dedup_report.json"
    with open(report_path, "w") as f:
        json.dump(stats, f, indent=2)
    logger.info("Report saved to %s", report_path)

    # Summary
    print(f"\n✓ {total_evidence} relationships → {len(claims)} unique claims")
    print(f"  ({stats['compression_ratio']}x compression)")
    print(f"  {len(multi_evidence)} claims backed by multiple evidence items")
    print(f"  {len(conflicts)} potential conflicts flagged for Day 19")


if __name__ == "__main__":
    main()