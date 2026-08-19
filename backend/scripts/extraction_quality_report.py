"""
extraction_quality_report.py

Summary statistics for the completed extraction run: totals per
category, null-attribution rates, and a few sanity checks. Run once
extraction is fully complete.
"""

import json
from pathlib import Path
from collections import Counter

BASE = Path(__file__).resolve().parent.parent.parent / "data" / "processed"
EXTRACTED_PATH = BASE / "extracted_entities.jsonl"


def generate_report():
    total_records = 0
    total_people = 0
    total_orgs = 0
    total_deals = 0
    total_decisions = 0
    total_relationships = 0

    decisions_null_made_by = 0
    relationships_by_type = Counter()
    org_types = Counter()

    with open(EXTRACTED_PATH, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            total_records += 1

            total_people += len(record.get("people", []))
            total_orgs += len(record.get("organizations", []))
            total_deals += len(record.get("deals", []))
            total_decisions += len(record.get("decisions", []))
            total_relationships += len(record.get("relationships", []))

            for d in record.get("decisions", []):
                if not d.get("made_by"):
                    decisions_null_made_by += 1

            for r in record.get("relationships", []):
                relationships_by_type[r.get("relationship_type", "unknown")] += 1

            for o in record.get("organizations", []):
                org_types[o.get("org_type") or "null"] += 1

    print("=" * 55)
    print("EXTRACTION QUALITY REPORT")
    print("=" * 55)
    print(f"Total emails extracted:      {total_records}")
    print()
    print(f"Total people mentions:       {total_people}")
    print(f"Total organizations:         {total_orgs}")
    print(f"Total deals:                 {total_deals}")
    print(f"Total decisions:             {total_decisions}")
    print(f"Total relationships:         {total_relationships}")
    print()
    print(f"Avg people/email:            {total_people/total_records:.2f}")
    print(f"Avg decisions/email:         {total_decisions/total_records:.2f}")
    print(f"Avg relationships/email:     {total_relationships/total_records:.2f}")
    print()
    print(f"Decisions with made_by=null: {decisions_null_made_by} "
          f"({decisions_null_made_by/total_decisions*100:.1f}% of decisions)" if total_decisions else "")
    print()
    print("Relationship types breakdown:")
    for rtype, count in relationships_by_type.most_common():
        print(f"  {rtype:20s} {count}")
    print()
    print("Organization types breakdown:")
    for otype, count in org_types.most_common():
        print(f"  {otype:20s} {count}")
    print("=" * 55)


if __name__ == "__main__":
    generate_report()