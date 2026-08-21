"""
Analyze known failure cases from the pipeline:
- 303 unverified evidence quotes (Day 8)
- 22 review queue items (Day 11)
- 6 rejected items (Day 11)

Categorize failure modes to understand extraction weaknesses.
"""
import json
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))


def analyze_unverified(base: Path, sources: dict):
    """Categorize why evidence quotes failed verification."""
    print("\n=== Unverified Evidence Analysis ===\n")
    
    categories = Counter()
    examples = {}
    
    input_file = base / "extractions_final.jsonl"
    if not input_file.exists():
        input_file = base / "extractions_gated.jsonl"
    
    with open(input_file) as f:
        for line in f:
            extraction = json.loads(line)
            mid = extraction["message_id"]
            source = sources.get(mid, {})
            body = source.get("body", "")
            
            for field in ["relationships"]:  # only relationships have evidence
                for item in extraction.get(field, []):
                    if item.get("evidence_verified") is False:
                        evidence = item.get("evidence", "")
                        
                        # Categorize the failure
                        if not evidence.strip():
                            cat = "empty_evidence"
                        elif evidence.lower() in body.lower():
                            cat = "case_mismatch_only"
                        elif len(evidence) < 20:
                            cat = "very_short_and_unmatched"
                        elif any(word not in body.lower() 
                                for word in evidence.lower().split()[:3]):
                            cat = "likely_paraphrased"
                        else:
                            cat = "whitespace_or_encoding"
                        
                        categories[cat] += 1
                        
                        if cat not in examples or len(examples[cat]) < 3:
                            if cat not in examples:
                                examples[cat] = []
                            examples[cat].append({
                                "message_id": mid,
                                "evidence": evidence[:150],
                            })
    
    print(f"Total unverified: {sum(categories.values())}\n")
    print("Categories:")
    for cat, count in categories.most_common():
        print(f"  {cat:>30}: {count}")
        if cat in examples:
            for ex in examples[cat][:2]:
                print(f"    example: \"{ex['evidence'][:80]}...\"")
    
    return dict(categories)


def analyze_review_queue(base: Path, sources: dict):
    """Analyze the 22 items in the review queue."""
    print("\n=== Review Queue Analysis ===\n")
    
    review_file = base / "review_queue.jsonl"
    if not review_file.exists():
        print("No review queue file found.")
        return {}
    
    items = []
    with open(review_file) as f:
        for line in f:
            items.append(json.loads(line))
    
    print(f"Total review items: {len(items)}\n")
    
    penalty_reasons = Counter()
    for entry in items:
        item = entry.get("item", {})
        for penalty_name, penalty_val in item.get("confidence_penalties", []):
            penalty_reasons[penalty_name] += 1
    
    print("Common penalty reasons in review items:")
    for reason, count in penalty_reasons.most_common():
        print(f"  {reason:>25}: {count}")
    
    # Show a few examples
    print(f"\nFirst 5 review items:")
    for entry in items[:5]:
        item = entry["item"]
        print(f"  {entry['field']}: "
              f"{item.get('person_a', '?')} --{item.get('relationship_type', '?')}--> "
              f"{item.get('person_b', '?')}")
        print(f"    confidence={item.get('confidence')}, "
              f"evidence_verified={item.get('evidence_verified')}")
        ev = (item.get("evidence") or "")[:80]
        if ev:
            print(f"    evidence: \"{ev}...\"")
    
    return dict(penalty_reasons)


def analyze_rejected(base: Path):
    """Analyze the 6 rejected items."""
    print("\n=== Rejected Items Analysis ===\n")
    
    reasons = Counter()
    
    input_file = base / "extractions_final.jsonl"
    if not input_file.exists():
        input_file = base / "extractions_gated.jsonl"
    
    with open(input_file) as f:
        for line in f:
            extraction = json.loads(line)
            for field in ["people", "organizations", "deals",
                         "decisions", "relationships"]:
                for item in extraction.get(field, []):
                    if item.get("status") == "rejected":
                        reason = item.get("gate_reason", "unknown")
                        reasons[reason] += 1
                        
                        # Print details
                        print(f"  {field}: {reason}")
                        if field == "relationships":
                            print(f"    {item.get('person_a', '?')} --> "
                                  f"{item.get('person_b', '?')}")
                            ev = (item.get("evidence") or "")[:80]
                            if ev:
                                print(f"    evidence: \"{ev}\"")
    
    print(f"\nTotal rejected: {sum(reasons.values())}")
    print("Reasons:")
    for reason, count in reasons.most_common():
        print(f"  {reason}: {count}")
    
    return dict(reasons)


def main():
    base = Path(__file__).parent.parent.parent / "data" / "processed"
    
    print("Loading source emails...")
    sources = {}
    with open(base / "extraction_subset.jsonl") as f:
        for line in f:
            email = json.loads(line)
            sources[email["message_id"]] = email
    
    unverified_cats = analyze_unverified(base, sources)
    review_reasons = analyze_review_queue(base, sources)
    rejected_reasons = analyze_rejected(base)
    
    # Save combined analysis
    analysis = {
        "unverified_categories": unverified_cats,
        "review_queue_penalties": review_reasons,
        "rejection_reasons": rejected_reasons,
    }
    
    report_path = base / "failure_analysis.json"
    with open(report_path, "w") as f:
        json.dump(analysis, f, indent=2)
    
    print(f"\nAnalysis saved: {report_path}")


if __name__ == "__main__":
    main()