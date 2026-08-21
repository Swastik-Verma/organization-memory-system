"""
Manual evaluation of extraction quality.

Selects a random sample of extractions, displays each one alongside 
the source email, and prompts the evaluator to score each item.

Produces a quality report with accuracy metrics.
"""
import json
import random
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))


def load_data(base: Path) -> tuple[list[dict], dict]:
    """Load extractions and source emails."""
    extractions = []
    input_file = base / "extractions_final.jsonl"
    if not input_file.exists():
        input_file = base / "extractions_gated.jsonl"
    
    with open(input_file) as f:
        for line in f:
            extractions.append(json.loads(line))
    
    sources = {}
    with open(base / "extraction_subset.jsonl") as f:
        for line in f:
            email = json.loads(line)
            sources[email["message_id"]] = email
    
    return extractions, sources


def display_email(source: dict):
    """Display the source email clearly."""
    print("\n" + "=" * 70)
    print("SOURCE EMAIL")
    print("=" * 70)
    print(f"Message-ID: {source.get('message_id', 'N/A')}")
    print(f"From:       {source.get('from_addr', 'N/A')}")
    print(f"To:         {source.get('to_addrs', 'N/A')}")
    print(f"Date:       {source.get('date', 'N/A')}")
    print(f"Subject:    {source.get('subject', 'N/A')}")
    print(f"\nBody:\n{source.get('body', '(empty)')[:2000]}")
    if len(source.get('body', '')) > 2000:
        print(f"\n... [truncated, full body is {len(source['body'])} chars]")


def display_extraction(extraction: dict):
    """Display the extraction results."""
    print("\n" + "-" * 70)
    print("EXTRACTION RESULTS")
    print("-" * 70)
    
    for field in ["people", "organizations", "deals", "decisions", "relationships"]:
        items = extraction.get(field, [])
        if not items:
            continue
        
        print(f"\n  {field.upper()} ({len(items)}):")
        for i, item in enumerate(items):
            conf = item.get("confidence", "N/A")
            status = item.get("status", "N/A")
            verified = item.get("evidence_verified", "N/A")
            
            if field == "people":
                print(f"    [{i}] {item.get('name', '?')} "
                      f"({item.get('email', 'no email')}) "
                      f"[conf={conf}, status={status}]")
            elif field == "organizations":
                print(f"    [{i}] {item.get('name', '?')} "
                      f"[conf={conf}, status={status}]")
            elif field == "deals":
                print(f"    [{i}] {item.get('name', '?')} "
                      f"[conf={conf}, status={status}]")
            elif field == "decisions":
                desc = item.get("description", "?")[:80]
                print(f"    [{i}] {desc} "
                      f"[conf={conf}, status={status}]")
            elif field == "relationships":
                src = item.get("person_a", "?")
                tgt = item.get("person_b", "?")
                rtype = item.get("relationship_type", "?")
                ev = item.get("evidence", "")[:60]
                print(f"    [{i}] {src} --{rtype}--> {tgt} "
                      f"[conf={conf}, verified={verified}]")
                if ev:
                    print(f"         evidence: \"{ev}...\"")


def score_item(field: str, index: int) -> str:
    """Prompt the evaluator to score one item."""
    while True:
        score = input(f"    Score {field}[{index}] "
                      f"(c=correct, p=partial, h=hallucinated, s=skip): ").strip().lower()
        if score in ("c", "p", "h", "s"):
            return {"c": "correct", "p": "partial", "h": "hallucinated", "s": "skip"}[score]
        print("      Invalid input. Use c/p/h/s.")


def evaluate_sample(extractions: list[dict], sources: dict,
                    sample_size: int = 50, seed: int = 42):
    """Run the interactive evaluation on a random sample."""
    random.seed(seed)
    
    # Filter to extractions that have at least some content
    non_empty = [e for e in extractions if any(
        e.get(f, []) for f in ["people", "organizations", "deals", 
                                "decisions", "relationships"]
    )]
    
    sample = random.sample(non_empty, min(sample_size, len(non_empty)))
    
    print(f"\nEvaluating {len(sample)} extractions (seed={seed})")
    print("Scoring: c=correct, p=partial, h=hallucinated, s=skip\n")
    
    all_scores = []
    field_scores = Counter()
    field_totals = Counter()
    missed_count = 0
    
    for email_idx, extraction in enumerate(sample):
        mid = extraction["message_id"]
        source = sources.get(mid)
        
        if not source:
            print(f"\nWARNING: No source for {mid}, skipping")
            continue
        
        print(f"\n{'#' * 70}")
        print(f"  EMAIL {email_idx + 1}/{len(sample)}")
        print(f"{'#' * 70}")
        
        display_email(source)
        display_extraction(extraction)
        
        print("\n  --- SCORING ---")
        
        for field in ["people", "organizations", "deals", 
                      "decisions", "relationships"]:
            for i, item in enumerate(extraction.get(field, [])):
                score = score_item(field, i)
                if score != "skip":
                    all_scores.append(score)
                    field_totals[field] += 1
                    if score == "correct":
                        field_scores[field] += 1
        
        # Ask about missed extractions
        missed = input("\n    Any facts in the email that were MISSED? "
                      "(enter count, or 0): ").strip()
        try:
            missed_count += int(missed)
        except ValueError:
            pass
        
        # Progress summary
        if all_scores:
            correct = all_scores.count("correct")
            total = len(all_scores)
            print(f"\n    Running accuracy: {correct}/{total} "
                  f"({correct/total*100:.1f}%)")
        
        cont = input("\n    Continue? (y/n): ").strip().lower()
        if cont == "n":
            break
    
    return all_scores, field_scores, field_totals, missed_count


def generate_report(all_scores, field_scores, field_totals, 
                    missed_count, sample_size):
    """Generate and print the evaluation report."""
    total = len(all_scores)
    if total == 0:
        print("No items scored.")
        return {}
    
    correct = all_scores.count("correct")
    partial = all_scores.count("partial")
    hallucinated = all_scores.count("hallucinated")
    
    accuracy = correct / total * 100
    hallucination_rate = hallucinated / total * 100
    
    print(f"\n{'=' * 70}")
    print(f"EXTRACTION QUALITY REPORT")
    print(f"{'=' * 70}")
    print(f"\nSample size: {sample_size} emails")
    print(f"Total items scored: {total}")
    print(f"Missed extractions noted: {missed_count}")
    
    print(f"\nOverall:")
    print(f"  Correct:      {correct:>5} ({accuracy:.1f}%)")
    print(f"  Partial:      {partial:>5} ({partial/total*100:.1f}%)")
    print(f"  Hallucinated: {hallucinated:>5} ({hallucination_rate:.1f}%)")
    
    print(f"\nPer-field accuracy:")
    for field in ["people", "organizations", "deals", 
                  "decisions", "relationships"]:
        ft = field_totals[field]
        if ft > 0:
            fc = field_scores[field]
            print(f"  {field:>15}: {fc}/{ft} ({fc/ft*100:.1f}%)")
    
    report = {
        "sample_size_emails": sample_size,
        "total_items_scored": total,
        "missed_extractions": missed_count,
        "overall": {
            "correct": correct,
            "partial": partial,
            "hallucinated": hallucinated,
            "accuracy_pct": round(accuracy, 2),
            "hallucination_rate_pct": round(hallucination_rate, 2),
        },
        "per_field": {
            field: {
                "correct": field_scores[field],
                "total": field_totals[field],
                "accuracy_pct": round(
                    field_scores[field] / field_totals[field] * 100, 2
                ) if field_totals[field] > 0 else None
            }
            for field in ["people", "organizations", "deals",
                         "decisions", "relationships"]
        },
    }
    
    return report


def main():
    base = Path(__file__).parent.parent.parent / "data" / "processed"
    
    sample_size = 50
    if len(sys.argv) > 1:
        try:
            sample_size = int(sys.argv[1])
        except ValueError:
            pass
    
    extractions, sources = load_data(base)
    print(f"Loaded {len(extractions)} extractions, {len(sources)} source emails")
    
    all_scores, field_scores, field_totals, missed_count = evaluate_sample(
        extractions, sources, sample_size
    )
    
    report = generate_report(all_scores, field_scores, field_totals, 
                            missed_count, sample_size)
    
    if report:
        report_path = base / "extraction_quality_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()