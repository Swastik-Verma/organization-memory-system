"""
Batch fuzzy entity resolution runner (Day 17).

Reads Day 16's entity_resolution_exact.json, finds fuzzy merge candidates,
applies auto-merges above the confidence threshold, and outputs updated
canonical entities + resolution map + merge operations.

Usage:
    cd ~/Layer_10_Project2/backend
    source venv/bin/activate
    python scripts/batch_fuzzy_resolution.py

Optional flags:
    --threshold 0.85     auto-merge confidence threshold (default 0.85)
    --dry-run            show candidates without merging
"""

import argparse
import json
import logging
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

sys.path.insert(0, str(BACKEND_DIR))

from src.deduplication.fuzzy_matcher import FuzzyMatcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Fuzzy entity resolution")
    parser.add_argument(
        "--threshold", type=float, default=0.85,
        help="Auto-merge confidence threshold (default: 0.85)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show candidates without applying merges",
    )
    args = parser.parse_args()

    data_dir = PROJECT_ROOT / "data" / "processed"
    exact_path = data_dir / "entity_resolution_exact.json"

    if not exact_path.exists():
        logger.error("entity_resolution_exact.json not found — run Day 16 first")
        sys.exit(1)

    # Load Day 16 output
    logger.info("Loading Day 16 exact resolution results…")
    with open(exact_path) as f:
        exact_data = json.load(f)

    entities = exact_data["canonical_entities"]
    resolution_map = exact_data["resolution_map"]

    logger.info(
        "Loaded %d canonical entities, %d resolution mappings",
        len(entities), len(resolution_map),
    )

    # Find candidates
    matcher = FuzzyMatcher(entities, resolution_map)
    candidates = matcher.find_candidates()

    # Show candidates
    above_threshold = [c for c in candidates if c.confidence >= args.threshold]
    below_threshold = [c for c in candidates if c.confidence < args.threshold]

    print("\n" + "=" * 70)
    print(f"FUZZY MERGE CANDIDATES (total: {len(candidates)})")
    print(f"  Above threshold ({args.threshold}): {len(above_threshold)}")
    print(f"  Below threshold: {len(below_threshold)}")
    print("=" * 70)

    # Show top candidates
    print(f"\nTop 20 candidates (will {'NOT ' if args.dry_run else ''}be merged):")
    for c in candidates[:20]:
        marker = "✓" if c.confidence >= args.threshold else "?"
        print(
            f"  {marker} [{c.strategy}] {c.confidence:.2f}  "
            f"'{c.source_name}' → '{c.target_name}'"
        )

    if len(candidates) > 20:
        print(f"  … and {len(candidates) - 20} more")

    if args.dry_run:
        print("\n(Dry run — no merges applied)")

        # Still save candidates for review
        candidates_path = data_dir / "fuzzy_candidates.json"
        with open(candidates_path, "w") as f:
            json.dump([c.to_dict() for c in candidates], f, indent=2)
        logger.info("Candidates saved to %s", candidates_path)
        return

    # Apply merges
    merged_count = matcher.apply_merges(candidates, auto_threshold=args.threshold)

    # Stats
    stats = matcher.get_stats()

    print("\n" + "=" * 70)
    print("FUZZY RESOLUTION RESULTS")
    print("=" * 70)
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # Show below-threshold candidates (potential Day 17 LLM targets)
    remaining = [
        c for c in candidates
        if c.confidence < args.threshold
        and c.source_id in matcher.entities
        and c.target_id in matcher.entities
    ]
    if remaining:
        print(f"\n  {len(remaining)} candidates below threshold (for LLM review):")
        for c in remaining[:10]:
            print(
                f"    ? [{c.strategy}] {c.confidence:.2f}  "
                f"'{c.source_name}' → '{c.target_name}'"
            )

    # Save results
    output = {
        "stats": stats,
        "canonical_entities": matcher.entities,
        "resolution_map": matcher.resolution_map,
        "merge_operations": matcher.get_merge_operations(),
        "below_threshold_candidates": [c.to_dict() for c in remaining],
        "config": {
            "auto_threshold": args.threshold,
            "dry_run": args.dry_run,
        },
    }

    results_path = data_dir / "entity_resolution_fuzzy.json"
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2)
    logger.info("Full results saved to %s", results_path)

    # Update the resolution map (supersedes Day 16's version)
    map_path = data_dir / "resolution_map.json"
    with open(map_path, "w") as f:
        json.dump(matcher.resolution_map, f, indent=2)
    logger.info(
        "Resolution map updated at %s (%d mappings)",
        map_path, len(matcher.resolution_map),
    )

    print(f"\n✓ {merged_count} fuzzy merges applied")
    print(f"  {stats['people_remaining']} canonical people remaining")
    print(f"  {stats['orgs_remaining']} canonical organizations remaining")
    if remaining:
        print(f"  {len(remaining)} candidates saved for manual/LLM review")


if __name__ == "__main__":
    main()