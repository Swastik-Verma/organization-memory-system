"""
Apply deterministic confidence scoring to all enriched extractions.
Produces scored extractions and a confidence distribution report.
"""
import json
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.extraction.confidence_scorer import score_extraction


def main():
    base = Path(__file__).parent.parent.parent / "data" / "processed"
    
    # Load source emails
    print("Loading source emails...")
    sources = {}
    with open(base / "extraction_subset.jsonl") as f:
        for line in f:
            email = json.loads(line)
            sources[email["message_id"]] = email
    print(f"  Loaded {len(sources)} source emails")
    
    # Load enriched extractions (with offsets from Day 8)
    print("Loading enriched extractions...")
    extractions = []
    with open(base / "extractions_with_offsets.jsonl") as f:
        for line in f:
            extractions.append(json.loads(line))
    print(f"  Loaded {len(extractions)} extractions")
    
    # Score each extraction
    output_path = base / "extractions_scored.jsonl"
    
    # Track distribution
    all_scores = []
    penalty_counts = Counter()
    field_scores = {
        "people": [], "organizations": [], "deals": [],
        "decisions": [], "relationships": []
    }
    
    with open(output_path, "w") as out_f:
        for i, extraction in enumerate(extractions):
            mid = extraction["message_id"]
            source = sources.get(mid)
            
            if not source:
                print(f"  WARNING: No source email for {mid}")
                out_f.write(json.dumps(extraction) + "\n")
                continue
            
            scored = score_extraction(extraction, source)
            
            # Collect stats
            for field in ["people", "organizations", "deals", 
                         "decisions", "relationships"]:
                for item in scored.get(field, []):
                    conf = item.get("confidence", 1.0)
                    all_scores.append(conf)
                    field_scores[field].append(conf)
                    for penalty_name, _ in item.get("confidence_penalties", []):
                        penalty_counts[penalty_name] += 1
            
            out_f.write(json.dumps(scored) + "\n")
            
            if (i + 1) % 2000 == 0:
                print(f"  Scored {i+1}/{len(extractions)}")
    
    # --- Distribution report ---
    print(f"\n=== Confidence Scoring Report ===")
    print(f"Total items scored: {len(all_scores)}")
    
    if all_scores:
        avg = sum(all_scores) / len(all_scores)
        sorted_scores = sorted(all_scores)
        p10 = sorted_scores[len(sorted_scores) // 10]
        p25 = sorted_scores[len(sorted_scores) // 4]
        p50 = sorted_scores[len(sorted_scores) // 2]
        
        print(f"Average confidence: {avg:.3f}")
        print(f"P10: {p10:.2f}  P25: {p25:.2f}  P50 (median): {p50:.2f}")
        
        # Bucket distribution
        buckets = {"0.0-0.3": 0, "0.3-0.5": 0, "0.5-0.7": 0, 
                   "0.7-0.9": 0, "0.9-1.0": 0}
        for s in all_scores:
            if s < 0.3:
                buckets["0.0-0.3"] += 1
            elif s < 0.5:
                buckets["0.3-0.5"] += 1
            elif s < 0.7:
                buckets["0.5-0.7"] += 1
            elif s < 0.9:
                buckets["0.7-0.9"] += 1
            else:
                buckets["0.9-1.0"] += 1
        
        print(f"\nDistribution:")
        for bucket, count in buckets.items():
            pct = count / len(all_scores) * 100
            bar = "█" * int(pct / 2)
            print(f"  {bucket}: {count:>6} ({pct:>5.1f}%) {bar}")
        
        # Per-field averages
        print(f"\nPer-field averages:")
        for field, scores in field_scores.items():
            if scores:
                field_avg = sum(scores) / len(scores)
                print(f"  {field:>15}: {field_avg:.3f}  (n={len(scores)})")
        
        # Penalty frequency
        print(f"\nPenalty frequency:")
        for penalty, count in penalty_counts.most_common():
            print(f"  {penalty:>25}: {count}")
    
    # Save report
    report = {
        "total_items": len(all_scores),
        "average_confidence": round(avg, 4) if all_scores else None,
        "distribution": buckets,
        "per_field_averages": {
            f: round(sum(s)/len(s), 4) if s else None 
            for f, s in field_scores.items()
        },
        "penalty_counts": dict(penalty_counts.most_common()),
    }
    
    report_path = base / "confidence_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nScored output:  {output_path}")
    print(f"Report saved:   {report_path}")


if __name__ == "__main__":
    main()