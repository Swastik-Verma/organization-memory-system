"""
Apply quality gates to all scored extractions.
Produces gated extractions and a separate review queue file.
"""
import json
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.extraction.quality_gate import (
    gate_extraction,
    STATUS_APPROVED,
    STATUS_REVIEW,
    STATUS_REJECTED,
    SOFT_THRESHOLD,
    HARD_THRESHOLD,
)


def main():
    base = Path(__file__).parent.parent.parent / "data" / "processed"
    
    input_file = base / "extractions_versioned.jsonl"
    if not input_file.exists():
        input_file = base / "extractions_scored.jsonl"
    
    print(f"Input: {input_file}")
    print(f"Thresholds: soft={SOFT_THRESHOLD}, hard={HARD_THRESHOLD}\n")
    
    output_file = base / "extractions_gated.jsonl"
    review_queue_file = base / "review_queue.jsonl"
    
    status_counts = Counter()
    reject_reasons = Counter()
    field_status = {
        "people": Counter(), "organizations": Counter(), "deals": Counter(),
        "decisions": Counter(), "relationships": Counter()
    }
    review_items = []
    
    with open(input_file) as f_in, open(output_file, "w") as f_out:
        for i, line in enumerate(f_in):
            extraction = json.loads(line)
            gated = gate_extraction(extraction)
            mid = gated["message_id"]
            
            for field in ["people", "organizations", "deals",
                         "decisions", "relationships"]:
                for idx, item in enumerate(gated.get(field, [])):
                    status = item.get("status")
                    status_counts[status] += 1
                    field_status[field][status] += 1
                    
                    if status == STATUS_REJECTED:
                        reason = item.get("gate_reason", "")
                        # Strip the confidence value for cleaner grouping
                        reason_key = reason.split(":")[0] + ":" + \
                                     (reason.split(":")[1] if ":" in reason else "")
                        reject_reasons[reason_key] += 1
                    
                    if status == STATUS_REVIEW:
                        review_items.append({
                            "message_id": mid,
                            "field": field,
                            "index": idx,
                            "item": item,
                        })
            
            f_out.write(json.dumps(gated) + "\n")
            
            if (i + 1) % 2000 == 0:
                print(f"  Gated {i+1} extractions")
    
    # Write review queue
    with open(review_queue_file, "w") as f:
        for entry in review_items:
            f.write(json.dumps(entry) + "\n")
    
    # --- Report ---
    total = sum(status_counts.values())
    print(f"\n=== Quality Gate Report ===")
    print(f"Total items gated: {total}\n")
    
    for status in [STATUS_APPROVED, STATUS_REVIEW, STATUS_REJECTED]:
        count = status_counts[status]
        pct = count / total * 100 if total else 0
        bar = "█" * int(pct / 2)
        print(f"  {status:>10}: {count:>7} ({pct:>6.2f}%) {bar}")
    
    print(f"\nPer-field breakdown:")
    for field, counts in field_status.items():
        field_total = sum(counts.values())
        if field_total == 0:
            continue
        appr = counts[STATUS_APPROVED]
        rev = counts[STATUS_REVIEW]
        rej = counts[STATUS_REJECTED]
        print(f"  {field:>15}: approved={appr:>6}  review={rev:>4}  rejected={rej:>5}"
              f"  (n={field_total})")
    
    if reject_reasons:
        print(f"\nRejection reasons:")
        for reason, count in reject_reasons.most_common():
            print(f"  {reason:>45}: {count}")
    
    # Save report
    report = {
        "thresholds": {"soft": SOFT_THRESHOLD, "hard": HARD_THRESHOLD},
        "total_items": total,
        "status_counts": dict(status_counts),
        "per_field": {f: dict(c) for f, c in field_status.items()},
        "rejection_reasons": dict(reject_reasons.most_common()),
        "review_queue_size": len(review_items),
    }
    
    report_path = base / "quality_gate_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nGated output:   {output_file}")
    print(f"Review queue:   {review_queue_file} ({len(review_items)} items)")
    print(f"Report saved:   {report_path}")


if __name__ == "__main__":
    main()