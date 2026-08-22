"""
Batch entity resolution runner — exact matching phase (Day 16).

Reads extractions_final.jsonl, collects all person and organization
mentions, resolves them via email matching and normalized name matching,
and outputs the resolution map + canonical entities + merge audit log.

Skips duplicate emails (from Day 15 duplicate_ids.json).

Person names are collected from THREE sources:
  - people list      (has name + email)
  - relationships    (person_a / person_b, name only)
  - decisions        (made_by, name only)

Organization names are collected from:
  - organizations list (has name + org_type)

Usage:
    cd ~/Layer_10_Project2/backend
    source venv/bin/activate
    python scripts/batch_entity_resolution.py
"""

import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

sys.path.insert(0, str(BACKEND_DIR))

from src.deduplication.entity_resolver import EntityResolver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_extractions(path: Path, duplicate_ids: set[str]) -> list[dict]:
    """Load extractions, skipping duplicate emails."""
    records = []
    skipped = 0
    with open(path) as f:
        for line in f:
            record = json.loads(line)
            if record["message_id"] in duplicate_ids:
                skipped += 1
                continue
            records.append(record)
    logger.info(
        "Loaded %d extractions (%d duplicates skipped)",
        len(records), skipped,
    )
    return records


def load_duplicate_ids(path: Path) -> set[str]:
    """Load the duplicate IDs from Day 15."""
    if not path.exists():
        logger.warning("duplicate_ids.json not found — no emails will be skipped")
        return set()
    with open(path) as f:
        ids = json.load(f)
    logger.info("Loaded %d duplicate IDs to skip", len(ids))
    return set(ids)


def collect_mentions(extractions: list[dict]) -> tuple[
    dict[tuple[str, str | None], int],   # person (name, email) → count
    dict[tuple[str, str | None], int],   # org (name, org_type) → count
]:
    """Collect all unique entity mentions with counts.

    Scans three sources for person names:
      - people list entries (name + email)
      - relationship endpoints (person_a, person_b — name only)
      - decision makers (made_by — name only)

    And one source for org names:
      - organizations list entries (name + org_type)
    """
    person_mentions: dict[tuple[str, str | None], int] = defaultdict(int)
    org_mentions: dict[tuple[str, str | None], int] = defaultdict(int)

    for record in extractions:
        # People from people list (with email)
        for person in record.get("people", []):
            name = person.get("name", "").strip()
            email = person.get("email")
            if email:
                email = email.strip().lower()
                if not email or "@" not in email:
                    email = None
            else:
                email = None
            if name:
                person_mentions[(name, email)] += 1

        # People from relationships (name only)
        for rel in record.get("relationships", []):
            for field_name in ("person_a", "person_b"):
                name = (rel.get(field_name) or "").strip()
                if name:
                    person_mentions[(name, None)] += 1

        # People from decisions (made_by, name only)
        for decision in record.get("decisions", []):
            made_by = (decision.get("made_by") or "").strip()
            if made_by:
                person_mentions[(made_by, None)] += 1

        # Organizations
        for org in record.get("organizations", []):
            name = (org.get("name") or "").strip()
            org_type = org.get("org_type")
            if name:
                org_mentions[(name, org_type)] += 1

    return person_mentions, org_mentions


def main():
    data_dir = PROJECT_ROOT / "data" / "processed"
    extractions_path = data_dir / "extractions_final.jsonl"
    dup_ids_path = data_dir / "duplicate_ids.json"

    if not extractions_path.exists():
        logger.error("extractions_final.jsonl not found at %s", extractions_path)
        sys.exit(1)

    # Load data
    duplicate_ids = load_duplicate_ids(dup_ids_path)
    extractions = load_extractions(extractions_path, duplicate_ids)

    # Collect all mentions
    person_mentions, org_mentions = collect_mentions(extractions)
    logger.info(
        "Collected %d unique person mentions, %d unique org mentions",
        len(person_mentions), len(org_mentions),
    )

    # --- Phase 1: Process person mentions with email FIRST ---
    # This ensures email-based merges happen before name-only mentions
    # arrive and might create separate entities prematurely.

    resolver = EntityResolver()

    with_email = [(name, email, count) for (name, email), count in person_mentions.items() if email]
    without_email = [(name, email, count) for (name, email), count in person_mentions.items() if not email]

    logger.info("Resolving %d person mentions with email…", len(with_email))
    for name, email, count in with_email:
        resolver.resolve_person(name, email, count)

    logger.info("Resolving %d person mentions without email…", len(without_email))
    for name, email, count in without_email:
        resolver.resolve_person(name, email, count)

    # --- Phase 2: Organizations ---
    logger.info("Resolving %d organization mentions…", len(org_mentions))
    for (name, org_type), count in org_mentions.items():
        resolver.resolve_organization(name, org_type, count)

    # Finalize (select best canonical names)
    resolver.finalize()

    # --- Output ---
    stats = resolver.get_stats()
    resolution_map = resolver.get_resolution_map()
    canonical_entities = resolver.get_canonical_entities()
    merge_log = resolver.get_merge_log()

    print("\n" + "=" * 60)
    print("ENTITY RESOLUTION — EXACT MATCHING RESULTS")
    print("=" * 60)
    for k, v in stats.items():
        if k == "shared_email_addresses":
            print(f"  {k}: {v[:10]}{'…' if len(v) > 10 else ''}")
        else:
            print(f"  {k}: {v}")
    print("=" * 60)

    # Show top merges (most aliases)
    all_entities = list(canonical_entities.values())
    multi_alias = [e for e in all_entities if len(e["aliases"]) > 1]
    multi_alias.sort(key=lambda e: len(e["aliases"]), reverse=True)

    print(f"\nTop 15 entities with most aliases (total multi-alias: {len(multi_alias)}):")
    for e in multi_alias[:15]:
        print(f"  {e['canonical_name']} ({e['entity_type']})")
        print(f"    Aliases: {e['aliases']}")
        if e['emails']:
            print(f"    Emails: {e['emails']}")
        print(f"    Mentions: {e['mention_count']}")

    # Save results
    output = {
        "stats": stats,
        "resolution_map": resolution_map,
        "canonical_entities": canonical_entities,
        "merge_log": merge_log,
    }

    results_path = data_dir / "entity_resolution_exact.json"
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2)
    logger.info("Results saved to %s", results_path)

    # Also save just the resolution map (lightweight, for ingestion)
    map_path = data_dir / "resolution_map.json"
    with open(map_path, "w") as f:
        json.dump(resolution_map, f, indent=2)
    logger.info(
        "Resolution map saved to %s (%d name→id mappings)",
        map_path, len(resolution_map),
    )

    # Summary
    print(f"\n✓ {stats['person_names_collapsed']} person name variants collapsed")
    print(f"  into {stats['canonical_people']} canonical people")
    print(f"✓ {stats['org_names_collapsed']} org name variants collapsed")
    print(f"  into {stats['canonical_orgs']} canonical organizations")
    print(f"✓ {stats['total_merges']} total merges logged to audit trail")


if __name__ == "__main__":
    main()