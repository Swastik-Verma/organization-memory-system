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
    affects_match_count = 0
    affects_total_count = 0
    empty_emails = 0

    person_name_counter = Counter()
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

            
            # Track emails with zero extractions
            if (len(record.get("people", [])) == 0
                and len(record.get("organizations", [])) == 0
                and len(record.get("deals", [])) == 0
                and len(record.get("decisions", [])) == 0
                and len(record.get("relationships", [])) == 0):
                empty_emails += 1

            # Track person name frequency for dedup preview
            for p in record.get("people", []):
                if p.get("name"):
                    person_name_counter[p["name"]] += 1

            # Track affects resolution rate
            people_names = {p.get("name", "").lower() for p in record.get("people", [])}
            org_names = {o.get("name", "").lower() for o in record.get("organizations", [])}
            all_names = people_names | org_names
            for d in record.get("decisions", []):
                for a in d.get("affects", []):
                    affects_total_count += 1
                    if a.lower() in all_names:
                        affects_match_count += 1

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

    print()
    print(f"Empty emails (zero extractions): {empty_emails} "
          f"({empty_emails/total_records*100:.1f}%)")
    print()
    print(f"Affects strings total:       {affects_total_count}")
    print(f"Affects matching a name:     {affects_match_count} "
          f"({affects_match_count/affects_total_count*100:.1f}%)" if affects_total_count else "")
    print(f"Affects unresolvable:        {affects_total_count - affects_match_count}")
    print()
    print("Top 50 person names (dedup preview):")
    for name, count in person_name_counter.most_common(50):
        print(f"  {name:40s} {count}")
    print()
    print("--- Graph size estimate ---")
    unique_people = len(person_name_counter)
    unique_orgs = len(org_types)
    print(f"Unique person name strings:  {unique_people}")
    print(f"Unique org name strings:     {unique_orgs}")
    print(f"Total nodes (rough):         ~{unique_people + unique_orgs + total_deals + total_decisions + total_records}")
    print(f"Total relationships (rough): ~{total_relationships + total_decisions * 2 + total_records}")
    print(f"512MB Neo4j heap:            {'comfortable' if (unique_people + unique_orgs) < 500000 else 'tight'}")


if __name__ == "__main__":
    generate_report()