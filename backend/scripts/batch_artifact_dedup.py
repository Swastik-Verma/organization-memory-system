"""
Batch artifact deduplication runner.

Reads extraction_subset.jsonl (10k parsed emails with bodies),
runs exact + near-duplicate detection, and saves results.

Output files:
  - data/processed/artifact_dedup_results.json   — full results + stats
  - data/processed/duplicate_ids.json            — flat list for ingestion lookup

Usage:
    cd ~/Layer_10_Project2/backend
    source venv/bin/activate
    python scripts/batch_artifact_dedup.py

Optional flags:
    --threshold 0.95    cosine similarity threshold (default 0.95)
    --exact-only        skip near-duplicate detection (fast, for testing)
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# --- path setup (matches project convention: parent.parent.parent for data/) ---
SCRIPT_DIR = Path(__file__).resolve().parent          # backend/scripts/
BACKEND_DIR = SCRIPT_DIR.parent                       # backend/
PROJECT_ROOT = BACKEND_DIR.parent                     # Layer_10_Project2/

sys.path.insert(0, str(BACKEND_DIR))

from src.deduplication.artifact_dedup import run_artifact_dedup
from src.parsing.noise_detector import detect_noise_regions, get_original_content

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_subset_emails(path: Path) -> list[dict]:
    """Load parsed emails from extraction_subset.jsonl."""
    emails = []
    with open(path) as f:
        for line in f:
            emails.append(json.loads(line))
    logger.info("Loaded %d emails from %s", len(emails), path.name)
    return emails


def enrich_with_original_content(emails: list[dict]) -> list[dict]:
    """Add 'original_content' field using the noise detector.

    Near-duplicate detection works better on noise-stripped bodies because
    forwarded copies share the same original content but have different
    forwarding headers prepended.
    """
    enriched_count = 0
    for email in emails:
        body = email.get("body") or ""
        if not body.strip():
            email["original_content"] = ""
            continue
        regions = detect_noise_regions(body)
        original = get_original_content(body, regions)
        email["original_content"] = original
        if regions:
            enriched_count += 1

    logger.info(
        "Noise-stripped %d/%d emails (%.1f%% had noise regions)",
        enriched_count, len(emails),
        100 * enriched_count / len(emails) if emails else 0,
    )
    return emails


def main():
    parser = argparse.ArgumentParser(description="Run artifact deduplication")
    parser.add_argument(
        "--threshold", type=float, default=0.95,
        help="Cosine similarity threshold for near-duplicates (default: 0.95)",
    )
    parser.add_argument(
        "--exact-only", action="store_true",
        help="Skip near-duplicate detection (exact hash only)",
    )
    args = parser.parse_args()

    data_dir = PROJECT_ROOT / "data" / "processed"
    subset_path = data_dir / "extraction_subset.jsonl"

    if not subset_path.exists():
        logger.error("extraction_subset.jsonl not found at %s", subset_path)
        sys.exit(1)

    # Load emails
    emails = load_subset_emails(subset_path)

    # Enrich with noise-stripped content (for better near-dup matching)
    if not args.exact_only:
        emails = enrich_with_original_content(emails)

    # Run dedup
    start = time.time()
    result = run_artifact_dedup(
        emails,
        near_dup_threshold=args.threshold,
        skip_near_duplicates=args.exact_only,
    )
    elapsed = time.time() - start

    # Print summary
    summary = result.summary()
    summary["elapsed_seconds"] = round(elapsed, 1)
    summary["threshold"] = args.threshold
    summary["total_emails"] = len(emails)
    summary["unique_emails"] = len(emails) - summary["total_duplicates_to_skip"]

    print("\n" + "=" * 60)
    print("ARTIFACT DEDUPLICATION RESULTS")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("=" * 60)

    # Print group details (if any found)
    for group in result.all_groups:
        print(f"\n  [{group.method}] Primary: {group.primary_id[:60]}…")
        print(f"    Duplicates: {len(group.duplicate_ids)}")
        print(f"    Similarity: {group.similarity}")
        print(f"    Reason: {group.reason}")

    # Save full results
    results_path = data_dir / "artifact_dedup_results.json"
    full_output = result.to_dict()
    full_output["config"] = {
        "threshold": args.threshold,
        "exact_only": args.exact_only,
        "total_emails": len(emails),
    }
    with open(results_path, "w") as f:
        json.dump(full_output, f, indent=2)
    logger.info("Full results saved to %s", results_path)

    # Save flat duplicate_ids list (for easy ingestion lookup)
    dup_ids_path = data_dir / "duplicate_ids.json"
    with open(dup_ids_path, "w") as f:
        json.dump(sorted(result.duplicate_ids), f, indent=2)
    logger.info("Duplicate IDs saved to %s (%d IDs)", dup_ids_path, len(result.duplicate_ids))

    # Summary for README
    if summary["total_duplicates_to_skip"] == 0:
        print("\n✓ No duplicates found. All 10,000 emails are unique.")
        print("  This confirms the Day 3 finding on the extraction subset.")
    else:
        print(f"\n⚠ Found {summary['total_duplicates_to_skip']} duplicate emails to skip.")
        print(f"  {summary['unique_emails']} unique emails will be loaded into Neo4j.")


if __name__ == "__main__":
    main()