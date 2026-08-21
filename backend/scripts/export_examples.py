"""
Export a small set of example extraction outputs to data/outputs/
for inclusion in the Git repository.

These examples demonstrate what the pipeline produces without
requiring the full dataset or API access to reproduce.
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    base = Path(__file__).parent.parent.parent / "data"
    processed = base / "processed"
    outputs = base / "outputs"
    outputs.mkdir(exist_ok=True)
    
    # --- 1. Example extractions (5 diverse emails) ---
    print("Selecting example extractions...")
    
    input_file = processed / "extractions_final.jsonl"
    if not input_file.exists():
        input_file = processed / "extractions_gated.jsonl"
    
    all_extractions = []
    with open(input_file) as f:
        for line in f:
            all_extractions.append(json.loads(line))
    
    # Pick 5 interesting ones: at least one with relationships, 
    # one with decisions, one with deals
    random.seed(42)
    
    examples = []
    
    # One with relationships
    for e in all_extractions:
        rels = [r for r in e.get("relationships", []) 
                if r.get("status") == "approved"]
        if len(rels) >= 2:
            examples.append(e)
            break
    
    # One with decisions
    for e in all_extractions:
        if e not in examples and len(e.get("decisions", [])) >= 2:
            examples.append(e)
            break
    
    # One with deals
    for e in all_extractions:
        if e not in examples and len(e.get("deals", [])) >= 1:
            examples.append(e)
            break
    
    # Two random ones for variety
    remaining = [e for e in all_extractions if e not in examples]
    non_empty = [e for e in remaining if any(
        e.get(f, []) for f in ["people", "organizations", "deals",
                                "decisions", "relationships"]
    )]
    examples.extend(random.sample(non_empty, min(2, len(non_empty))))
    
    with open(outputs / "example_extractions.json", "w") as f:
        json.dump(examples, f, indent=2)
    print(f"  Saved {len(examples)} example extractions")
    
    # --- 2. Pipeline report ---
    report_file = processed / "pipeline_report.json"
    if report_file.exists():
        with open(report_file) as f:
            report = json.load(f)
        with open(outputs / "pipeline_report.json", "w") as f:
            json.dump(report, f, indent=2)
        print("  Saved pipeline report")
    
    # --- 3. Confidence report ---
    conf_file = processed / "confidence_report.json"
    if conf_file.exists():
        with open(conf_file) as f:
            report = json.load(f)
        with open(outputs / "confidence_report.json", "w") as f:
            json.dump(report, f, indent=2)
        print("  Saved confidence report")
    
    # --- 4. Quality gate report ---
    gate_file = processed / "quality_gate_report.json"
    if gate_file.exists():
        with open(gate_file) as f:
            report = json.load(f)
        with open(outputs / "quality_gate_report.json", "w") as f:
            json.dump(report, f, indent=2)
        print("  Saved quality gate report")
    
    # --- 5. Failure analysis ---
    failure_file = processed / "failure_analysis.json"
    if failure_file.exists():
        with open(failure_file) as f:
            report = json.load(f)
        with open(outputs / "failure_analysis.json", "w") as f:
            json.dump(report, f, indent=2)
        print("  Saved failure analysis")
    
    # --- 6. Summary statistics ---
    summary = {
        "corpus": {
            "total_emails_parsed": 517389,
            "extraction_subset": 10000,
            "mailboxes_selected": 10,
        },
        "extraction": {
            "model": "gemini-3.1-flash-lite",
            "prompt_version": "v2",
            "total_items_extracted": 152283,
            "breakdown": {
                "people": 98611,
                "organizations": 28723,
                "deals": 4781,
                "decisions": 12331,
                "relationships": 7837,
            },
        },
        "evidence_verification": {
            "total_quotes": 7836,
            "verified": 7533,
            "rate_pct": 96.1,
        },
        "confidence_scoring": {
            "average": 0.889,
            "median": 0.90,
        },
        "quality_gate": {
            "approved": 152255,
            "review": 22,
            "rejected": 6,
        },
    }
    
    with open(outputs / "summary_statistics.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("  Saved summary statistics")
    
    print(f"\nAll outputs saved to {outputs}/")
    print("These files should be committed to the repo.")


if __name__ == "__main__":
    main()