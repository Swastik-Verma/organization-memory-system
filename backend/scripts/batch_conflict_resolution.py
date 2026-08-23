"""
Batch conflict resolution runner (Day 19).

Reads Day 18's conflicts and deduplicated claims, classifies each conflict,
auto-resolves temporal successions, flags contradictions for review, and
writes updated claims with validity windows closed.

Reads:
  - data/processed/deduplicated_claims.jsonl   (Day 18)
  - data/processed/claim_conflicts.json        (Day 18)
  - data/processed/extractions_final.jsonl     (for decision reversals)
  - data/processed/duplicate_ids.json          (Day 15)

Outputs:
  - data/processed/resolved_claims.jsonl       ★ CANONICAL claims for Neo4j
  - data/processed/conflict_resolutions.json   (classification + audit trail)
  - data/processed/conflict_review_queue.json  (contradictions needing humans)
  - data/processed/decision_reversals.json     (flagged reversal decisions)

Usage:
    cd ~/Layer_10_Project2/backend
    source venv/bin/activate
    python scripts/batch_conflict_resolution.py
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

from src.deduplication.conflict_resolver import (
    resolve_conflicts,
    apply_updates,
    detect_decision_reversals,
)

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


def load_json(path: Path):
    with open(path) as f:
        return json.load(f)


def main():
    data_dir = PROJECT_ROOT / "data" / "processed"

    claims_path = data_dir / "deduplicated_claims.jsonl"
    conflicts_path = data_dir / "claim_conflicts.json"
    extractions_path = data_dir / "extractions_final.jsonl"
    dup_ids_path = data_dir / "duplicate_ids.json"

    for required in [claims_path, conflicts_path]:
        if not required.exists():
            logger.error("Required file not found: %s — run Day 18 first", required)
            sys.exit(1)

    # --- Load ---

    logger.info("Loading deduplicated claims…")
    claims = load_jsonl(claims_path)
    logger.info("Loaded %d claims", len(claims))

    logger.info("Loading conflicts…")
    conflicts_data = load_json(conflicts_path)
    conflicts = conflicts_data.get("conflicts", [])
    logger.info("Loaded %d conflicts", len(conflicts))

    duplicate_ids = set()
    if dup_ids_path.exists():
        duplicate_ids = set(load_json(dup_ids_path))

    # --- Resolve conflicts ---

    logger.info("Classifying and resolving conflicts…")
    resolved, updates = resolve_conflicts(conflicts, claims)

    # --- Apply updates to claims ---

    logger.info("Applying updates to claims…")
    updated_claims = apply_updates(claims, updates)

    # --- Detect decision reversals ---

    reversals = []
    if extractions_path.exists():
        logger.info("Scanning decisions for reversal language…")
        extractions = load_jsonl(extractions_path)
        reversals = detect_decision_reversals(extractions, duplicate_ids)

    # --- Statistics ---

    classification_counts = Counter(r.classification for r in resolved)
    resolution_counts = Counter(r.resolution for r in resolved)

    status_counts = Counter(c.get("status", "current") for c in updated_claims)
    closed_windows = sum(
        1 for c in updated_claims if c.get("valid_to") is not None
    )

    review_queue = [r for r in resolved if r.resolution == "needs_review"]

    stats = {
        "total_conflicts_input": len(conflicts),
        "classifications": dict(classification_counts),
        "resolutions": dict(resolution_counts),
        "claims_updated": len(updates),
        "claims_with_closed_windows": closed_windows,
        "claim_status_distribution": dict(status_counts),
        "conflicts_needing_review": len(review_queue),
        "decision_reversals_detected": len(reversals),
    }

    print("\n" + "=" * 65)
    print("CONFLICT RESOLUTION RESULTS")
    print("=" * 65)
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print("=" * 65)

    # Show auto-resolved examples
    auto = [r for r in resolved if r.resolution == "auto_resolved"]
    if auto:
        print(f"\nAuto-resolved temporal successions (showing up to 10 of {len(auto)}):")
        for r in auto[:10]:
            objects = [c["object_name"] for c in r.claims]
            print(f"  {r.subject_name} {r.claim_type}: {' → '.join(objects)}")
            print(f"    superseded: {len(r.superseded_claim_ids)}, "
                  f"current: {r.current_claim_id}")

    # Show review queue
    if review_queue:
        print(f"\nNeeds human review (showing up to 10 of {len(review_queue)}):")
        for r in review_queue[:10]:
            objects = [c["object_name"] for c in r.claims]
            print(f"  [{r.classification}] {r.subject_name} "
                  f"{r.claim_type} → {objects}")
            print(f"    {r.reason}")

    # Show dismissed
    dismissed = [r for r in resolved if r.resolution == "dismissed"]
    if dismissed:
        print(f"\nDismissed as non-conflicts: {len(dismissed)}")
        type_counts = Counter(r.claim_type for r in dismissed)
        for t, count in type_counts.most_common():
            print(f"    {t}: {count}")

    # Show reversals
    if reversals:
        print(f"\nDecision reversals detected (showing up to 5 of {len(reversals)}):")
        for rev in reversals[:5]:
            desc = rev.description[:80]
            print(f"  [{rev.matched_pattern}] {desc}…")

    # --- Save outputs ---

    # Updated claims (CANONICAL for Neo4j)
    resolved_claims_path = data_dir / "resolved_claims.jsonl"
    with open(resolved_claims_path, "w") as f:
        for claim in updated_claims:
            f.write(json.dumps(claim) + "\n")
    logger.info(
        "Saved %d resolved claims to %s", len(updated_claims), resolved_claims_path
    )

    # Full resolution audit trail
    resolutions_path = data_dir / "conflict_resolutions.json"
    with open(resolutions_path, "w") as f:
        json.dump({
            "stats": stats,
            "resolutions": [r.to_dict() for r in resolved],
            "claim_updates": {k: v.to_dict() for k, v in updates.items()},
        }, f, indent=2)
    logger.info("Saved resolution audit trail to %s", resolutions_path)

    # Review queue (for Week 7 frontend, Day 44)
    review_path = data_dir / "conflict_review_queue.json"
    with open(review_path, "w") as f:
        json.dump({
            "total": len(review_queue),
            "conflicts": [r.to_dict() for r in review_queue],
        }, f, indent=2)
    logger.info("Saved review queue (%d items) to %s", len(review_queue), review_path)

    # Decision reversals
    reversals_path = data_dir / "decision_reversals.json"
    with open(reversals_path, "w") as f:
        json.dump({
            "total": len(reversals),
            "reversals": [r.to_dict() for r in reversals],
        }, f, indent=2)
    logger.info("Saved %d decision reversals to %s", len(reversals), reversals_path)

    # --- Summary ---

    print(f"\n✓ {len(conflicts)} conflicts classified")
    print(f"  {resolution_counts.get('dismissed', 0)} dismissed (non-exclusive types)")
    print(f"  {resolution_counts.get('auto_resolved', 0)} auto-resolved (temporal changes)")
    print(f"  {resolution_counts.get('needs_review', 0)} flagged for human review")
    print(f"\n✓ {closed_windows} claims have closed validity windows")
    print(f"✓ resolved_claims.jsonl is now the canonical claim file for Neo4j")


if __name__ == "__main__":
    main()