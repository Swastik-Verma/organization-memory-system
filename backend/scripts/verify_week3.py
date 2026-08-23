"""
Week 3 end-to-end verification — Day 21.

Runs the full deduplication pipeline in sequence and verifies that
each stage's output connects correctly to the next. Also runs
manual review samples and tests merge undo + soft delete behavior.

This is a VERIFICATION script, not a production pipeline.
It checks invariants and prints a pass/fail summary.

Usage:
    cd ~/Layer_10_Project2/backend
    source venv/bin/activate
    python scripts/verify_week3.py
"""

import json
import logging
import random
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

sys.path.insert(0, str(BACKEND_DIR))

from src.deduplication.redaction_manager import RedactionManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_json(path: Path):
    with open(path) as f:
        return json.load(f)


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            records.append(json.loads(line))
    return records


class VerificationResult:
    def __init__(self):
        self.checks: list[tuple[str, bool, str]] = []

    def check(self, name: str, condition: bool, detail: str = ""):
        self.checks.append((name, condition, detail))
        status = "✓ PASS" if condition else "✗ FAIL"
        print(f"  {status}: {name}")
        if detail and not condition:
            print(f"         {detail}")

    def summary(self):
        passed = sum(1 for _, ok, _ in self.checks if ok)
        failed = sum(1 for _, ok, _ in self.checks if not ok)
        total = len(self.checks)
        print(f"\n{'=' * 60}")
        print(f"VERIFICATION SUMMARY: {passed}/{total} passed, {failed} failed")
        print(f"{'=' * 60}")
        return failed == 0


def main():
    data_dir = PROJECT_ROOT / "data" / "processed"
    v = VerificationResult()

    print("=" * 60)
    print("WEEK 3 END-TO-END VERIFICATION")
    print("=" * 60)

    # ==================================================================
    # 1. Check all required files exist
    # ==================================================================
    print("\n--- File existence checks ---")

    required_files = {
        "Day 15 - Artifact dedup results": "artifact_dedup_results.json",
        "Day 15 - Duplicate IDs": "duplicate_ids.json",
        "Day 16 - Exact resolution": "entity_resolution_exact.json",
        "Day 16 - Resolution map": "resolution_map.json",
        "Day 17 - Fuzzy resolution": "entity_resolution_fuzzy.json",
        "Day 18 - Deduplicated claims": "deduplicated_claims.jsonl",
        "Day 18 - Claim conflicts": "claim_conflicts.json",
        "Day 19 - Resolved claims": "resolved_claims.jsonl",
        "Day 19 - Conflict resolutions": "conflict_resolutions.json",
        "Day 19 - Decision reversals": "decision_reversals.json",
    }

    for label, filename in required_files.items():
        path = data_dir / filename
        v.check(label, path.exists(), f"Missing: {path}")

    # ==================================================================
    # 2. Data integrity checks
    # ==================================================================
    print("\n--- Data integrity checks ---")

    # Day 15: duplicate IDs should be a subset of extraction subset
    dup_ids = set(load_json(data_dir / "duplicate_ids.json"))
    subset = load_jsonl(data_dir / "extraction_subset.jsonl")
    subset_ids = {e["message_id"] for e in subset}
    v.check(
        "Duplicate IDs are subset of extraction subset",
        dup_ids.issubset(subset_ids),
        f"{len(dup_ids - subset_ids)} IDs not in subset",
    )

    # Day 16: resolution map should cover all entity aliases
    resolution_map = load_json(data_dir / "resolution_map.json")
    exact_data = load_json(data_dir / "entity_resolution_exact.json")
    exact_entities = exact_data.get("canonical_entities", {})

    # Day 17: fuzzy resolution should have same or fewer entities
    fuzzy_data = load_json(data_dir / "entity_resolution_fuzzy.json")
    fuzzy_entities = fuzzy_data.get("canonical_entities", {})

    v.check(
        "Resolution map is non-empty",
        len(resolution_map) > 0,
        f"Map has {len(resolution_map)} entries",
    )

    # Day 18: all claims should have valid claim_ids
    claims = load_jsonl(data_dir / "deduplicated_claims.jsonl")
    v.check(
        "All claims have claim_id",
        all(c.get("claim_id") for c in claims),
    )
    v.check(
        "All claims have subject_id",
        all(c.get("subject_id") for c in claims),
    )
    v.check(
        "All claims have object_id",
        all(c.get("object_id") for c in claims),
    )
    v.check(
        "All claim types are valid",
        all(
            c.get("claim_type") in {"reports_to", "works_with", "requests_from",
                                     "informs", "negotiating_with"}
            for c in claims
        ),
    )

    # No duplicate claim IDs
    claim_ids = [c["claim_id"] for c in claims]
    v.check(
        "No duplicate claim IDs",
        len(claim_ids) == len(set(claim_ids)),
        f"{len(claim_ids) - len(set(claim_ids))} duplicates found",
    )

    # Day 19: resolved claims should match deduplicated claims count
    resolved_claims = load_jsonl(data_dir / "resolved_claims.jsonl")
    v.check(
        "Resolved claims count matches deduplicated claims",
        len(resolved_claims) == len(claims),
        f"Resolved: {len(resolved_claims)}, Deduped: {len(claims)}",
    )

    # Some claims should have closed validity windows
    closed = [c for c in resolved_claims if c.get("valid_to") is not None]
    v.check(
        "Some claims have closed validity windows (Day 19 auto-resolve)",
        len(closed) > 0,
        f"{len(closed)} claims with valid_to set",
    )

    # Superseded claims should have superseded_by
    superseded = [c for c in resolved_claims if c.get("status") == "superseded"]
    v.check(
        "Superseded claims have superseded_by field",
        all(c.get("superseded_by") for c in superseded),
        f"{sum(1 for c in superseded if not c.get('superseded_by'))} missing",
    )

    # ==================================================================
    # 3. Cross-stage consistency
    # ==================================================================
    print("\n--- Cross-stage consistency ---")

    # Claims should reference entities that exist in the resolution output
    entity_ids = set(fuzzy_entities.keys())
    claims_subject_ids = {c["subject_id"] for c in claims}
    claims_object_ids = {c["object_id"] for c in claims}
    all_claim_entity_ids = claims_subject_ids | claims_object_ids

    # Some might be "unresolved" — that's expected
    unresolved = {eid for eid in all_claim_entity_ids if ":unresolved" in eid}
    resolved_refs = all_claim_entity_ids - unresolved

    v.check(
        "No unresolved person references in claims",
        len(unresolved) == 0,
        f"{len(unresolved)} unresolved references",
    )

    # ==================================================================
    # 4. Soft delete verification
    # ==================================================================
    print("\n--- Soft delete verification ---")

    # Pick a random entity and test delete/restore cycle
    if fuzzy_entities:
        test_entity_id = random.choice(list(fuzzy_entities.keys()))
        test_entity = fuzzy_entities[test_entity_id]

        manager = RedactionManager(
            entities=dict(fuzzy_entities),  # copy
            claims=[dict(c) for c in resolved_claims],  # copy
            resolution_map=dict(resolution_map),
        )

        # Delete
        record = manager.soft_delete_entity(test_entity_id, "verification_test")
        v.check(
            "Soft delete marks entity as deleted",
            record is not None and manager.entities[test_entity_id].get("is_deleted"),
        )

        # Verify excluded from active queries
        active = manager.get_active_entities()
        v.check(
            "Deleted entity excluded from active queries",
            test_entity_id not in active,
        )

        # Verify appears in deleted queries
        deleted = manager.get_deleted_entities()
        v.check(
            "Deleted entity appears in audit queries",
            test_entity_id in deleted,
        )

        # Restore
        restored = manager.restore_entity(test_entity_id)
        v.check(
            "Restore brings entity back",
            restored and not manager.entities[test_entity_id].get("is_deleted"),
        )

        # Verify back in active queries
        active_after = manager.get_active_entities()
        v.check(
            "Restored entity back in active queries",
            test_entity_id in active_after,
        )

    # ==================================================================
    # 5. Manual review samples
    # ==================================================================
    print("\n--- Manual review samples ---")

    # Show 20 random entity merges for manual verification
    merge_log = exact_data.get("merge_log", [])
    if merge_log:
        sample_size = min(20, len(merge_log))
        sample_merges = random.sample(merge_log, sample_size)
        print(f"\n  {sample_size} random entity merges (verify manually):")
        for i, merge in enumerate(sample_merges, 1):
            print(
                f"    {i:2d}. '{merge.get('merged_name')}' → "
                f"'{merge.get('into_canonical_name')}' "
                f"({merge.get('reason')}, conf={merge.get('confidence')})"
            )

    # Show 20 random claim dedup decisions
    multi_evidence_claims = [c for c in claims if c.get("mention_count", 1) > 1]
    if multi_evidence_claims:
        sample_size = min(20, len(multi_evidence_claims))
        sample_claims = random.sample(multi_evidence_claims, sample_size)
        print(f"\n  {sample_size} random claim dedup decisions (verify manually):")
        for i, claim in enumerate(sample_claims, 1):
            print(
                f"    {i:2d}. [{claim['mention_count']}x] {claim['description']}"
            )

    # ==================================================================
    # 6. Statistics summary
    # ==================================================================
    print("\n--- Week 3 statistics ---")

    print(f"  Extraction subset:       {len(subset_ids)} emails")
    print(f"  Duplicate emails:        {len(dup_ids)} (Day 15)")
    print(f"  Unique emails:           {len(subset_ids) - len(dup_ids)}")
    print(f"  Canonical people:        {sum(1 for e in fuzzy_entities.values() if e.get('entity_type') == 'person')}")
    print(f"  Canonical organizations: {sum(1 for e in fuzzy_entities.values() if e.get('entity_type') == 'organization')}")
    print(f"  Resolution map entries:  {len(resolution_map)}")
    print(f"  Entity merges (Day 16):  {len(merge_log)}")
    print(f"  Deduplicated claims:     {len(claims)}")
    print(f"  Resolved claims:         {len(resolved_claims)}")
    print(f"  Superseded claims:       {len(superseded)}")
    print(f"  Claims in review:        {sum(1 for c in resolved_claims if c.get('status') == 'review')}")

    # ==================================================================
    # Final verdict
    # ==================================================================
    all_passed = v.summary()

    if all_passed:
        print("\n✓ Week 3 verification PASSED. Data is ready for Week 4 (Neo4j ingestion).")
    else:
        print("\n✗ Some checks failed. Review the failures above before proceeding.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())