"""
Unified enrichment pipeline — runs all post-extraction enrichment steps
in sequence and produces a single fully-enriched output file.

Steps (in order):
1. Evidence verification (Day 8) — verify quotes, compute offsets
2. Confidence scoring (Day 9) — deterministic field-aware scoring
3. Quality gating (Day 11) — route into approved/review/rejected
4. Version stamping (Day 10) — add prompt hash and model name

Input:  extracted_entities.jsonl + extraction_subset.jsonl
Output: extractions_final.jsonl (single file with all enrichments)
"""
import json
import sys
import time
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extraction.evidence_verifier import verify_extraction
from src.extraction.confidence_scorer import score_extraction
from src.extraction.quality_gate import gate_extraction, STATUS_APPROVED, STATUS_REVIEW, STATUS_REJECTED
from src.extraction.version_manager import compute_prompt_hash
from src.extraction.prompts import EXTRACTION_INSTRUCTIONS

# The model used for extraction
MODEL_NAME = "gemini-3.1-flash-lite"


def load_source_emails(path: Path) -> dict:
    """Load source emails keyed by message_id."""
    sources = {}
    with open(path) as f:
        for line in f:
            email = json.loads(line)
            sources[email["message_id"]] = email
    return sources


def run_pipeline():
    base = Path(__file__).parent.parent.parent / "data" / "processed"
    
    # --- Configuration ---
    input_file = base / "extracted_entities.jsonl"
    source_file = base / "extraction_subset.jsonl"
    output_file = base / "extractions_final.jsonl"
    report_file = base / "pipeline_report.json"
    review_file = base / "review_queue.jsonl"
    
    prompt_hash = compute_prompt_hash(EXTRACTION_INSTRUCTIONS)
    
    print("=== Enrichment Pipeline ===")
    print(f"Input:        {input_file}")
    print(f"Sources:      {source_file}")
    print(f"Prompt hash:  {prompt_hash}")
    print(f"Model:        {MODEL_NAME}\n")
    
    # --- Load data ---
    print("Loading source emails...")
    sources = load_source_emails(source_file)
    print(f"  Loaded {len(sources)} source emails")
    
    print("Loading raw extractions...")
    extractions = []
    with open(input_file) as f:
        for line in f:
            extractions.append(json.loads(line))
    print(f"  Loaded {len(extractions)} extractions\n")
    
    # --- Tracking ---
    total_quotes = 0
    verified_quotes = 0
    all_confidences = []
    status_counts = Counter()
    review_items = []
    
    start_time = time.time()
    
    # --- Process each extraction ---
    with open(output_file, "w") as f_out:
        for i, extraction in enumerate(extractions):
            mid = extraction["message_id"]
            source = sources.get(mid)
            
            if not source:
                print(f"  WARNING: No source email for {mid}")
                f_out.write(json.dumps(extraction) + "\n")
                continue
            
            # Step 1: Evidence verification
            report = verify_extraction(extraction, source)
            total_quotes += report["total_quotes"]
            verified_quotes += report["verified"]
            
            # Apply verification results to extraction
            for detail in report["details"]:
                field = detail["field"]
                idx = detail["index"]
                if idx < len(extraction.get(field, [])):
                    extraction[field][idx]["char_start"] = detail["char_start"]
                    extraction[field][idx]["char_end"] = detail["char_end"]
                    extraction[field][idx]["evidence_verified"] = detail["verified"]
            
            # Step 2: Confidence scoring
            extraction = score_extraction(extraction, source)
            
            # Step 3: Quality gating
            extraction = gate_extraction(extraction)
            
            # Step 4: Version stamping
            extraction["prompt_version"] = prompt_hash
            extraction["model_name"] = MODEL_NAME
            
            # Collect stats
            for field in ["people", "organizations", "deals", 
                         "decisions", "relationships"]:
                for idx, item in enumerate(extraction.get(field, [])):
                    conf = item.get("confidence", 1.0)
                    all_confidences.append(conf)
                    status = item.get("status", "unknown")
                    status_counts[status] += 1
                    
                    if status == STATUS_REVIEW:
                        review_items.append({
                            "message_id": mid,
                            "field": field,
                            "index": idx,
                            "item": item,
                        })
            
            f_out.write(json.dumps(extraction) + "\n")
            
            if (i + 1) % 2000 == 0:
                elapsed = time.time() - start_time
                print(f"  Processed {i+1}/{len(extractions)} "
                      f"({elapsed:.1f}s elapsed)")
    
    # Write review queue
    with open(review_file, "w") as f:
        for entry in review_items:
            f.write(json.dumps(entry) + "\n")
    
    # --- Report ---
    elapsed = time.time() - start_time
    verify_rate = (verified_quotes / total_quotes * 100) if total_quotes else 0
    avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0
    
    print(f"\n=== Pipeline Report ===")
    print(f"Processed {len(extractions)} extractions in {elapsed:.1f}s")
    print(f"\nEvidence verification: {verified_quotes}/{total_quotes} "
          f"({verify_rate:.1f}%)")
    print(f"Average confidence:   {avg_conf:.3f}")
    print(f"\nQuality gate:")
    for status in [STATUS_APPROVED, STATUS_REVIEW, STATUS_REJECTED]:
        count = status_counts[status]
        total = sum(status_counts.values())
        pct = count / total * 100 if total else 0
        print(f"  {status:>10}: {count:>7} ({pct:.2f}%)")
    print(f"\nReview queue: {len(review_items)} items")
    print(f"Output:       {output_file}")
    
    # Save report
    report = {
        "total_extractions": len(extractions),
        "processing_time_seconds": round(elapsed, 1),
        "evidence_verification": {
            "total_quotes": total_quotes,
            "verified": verified_quotes,
            "rate_pct": round(verify_rate, 2),
        },
        "confidence": {
            "average": round(avg_conf, 4),
        },
        "quality_gate": dict(status_counts),
        "review_queue_size": len(review_items),
        "version": {
            "prompt_hash": prompt_hash,
            "model_name": MODEL_NAME,
        },
    }
    
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"Report:       {report_file}")


if __name__ == "__main__":
    run_pipeline()