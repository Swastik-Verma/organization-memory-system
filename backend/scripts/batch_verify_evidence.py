"""
Verify all extraction evidence quotes against source email bodies.
Produces a verification report and an enriched extractions file with offsets.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.extraction.evidence_verifier import verify_extraction

def main():
    base = Path(__file__).parent.parent.parent / "data" / "processed"
    
    # Load source emails (keyed by message_id for lookup)
    print("Loading source emails...")
    sources = {}
    with open(base / "extraction_subset.jsonl") as f:
        for line in f:
            email = json.loads(line)
            sources[email["message_id"]] = email
    print(f"  Loaded {len(sources)} source emails")
    
    # Load extractions
    print("Loading extractions...")
    extractions = []
    with open(base / "extracted_entities.jsonl") as f:
        for line in f:
            extractions.append(json.loads(line))
    print(f"  Loaded {len(extractions)} extractions")
    
    # Verify each extraction
    total_quotes = 0
    total_verified = 0
    total_unverified = 0
    unverified_examples = []
    
    enriched_output = base / "extractions_with_offsets.jsonl"
    verification_report = base / "evidence_verification_report.json"
    
    with open(enriched_output, "w") as out_f:
        for i, extraction in enumerate(extractions):
            mid = extraction["message_id"]
            source = sources.get(mid)
            
            if not source:
                print(f"  WARNING: No source email for {mid}")
                continue
            
            report = verify_extraction(extraction, source)
            total_quotes += report["total_quotes"]
            total_verified += report["verified"]
            total_unverified += report["unverified"]
            
            # Enrich the extraction with offsets
            for detail in report["details"]:
                field = detail["field"]
                idx = detail["index"]
                if idx < len(extraction.get(field, [])):
                    extraction[field][idx]["char_start"] = detail["char_start"]
                    extraction[field][idx]["char_end"] = detail["char_end"]
                    extraction[field][idx]["evidence_verified"] = detail["verified"]
            
            # Collect unverified examples (first 20)
            if report["unverified"] > 0 and len(unverified_examples) < 20:
                for d in report["details"]:
                    if not d["verified"] and len(unverified_examples) < 20:
                        unverified_examples.append({
                            "message_id": mid,
                            "field": d["field"],
                            "quote": d["quote"][:200],
                        })
            
            out_f.write(json.dumps(extraction) + "\n")
            
            if (i + 1) % 1000 == 0:
                rate = (total_verified / total_quotes * 100) if total_quotes else 0
                print(f"  Processed {i+1}/{len(extractions)} — "
                      f"verification rate: {rate:.1f}%")
    
    # Summary
    rate = (total_verified / total_quotes * 100) if total_quotes else 0
    summary = {
        "total_extractions": len(extractions),
        "total_quotes": total_quotes,
        "verified": total_verified,
        "unverified": total_unverified,
        "verification_rate_pct": round(rate, 2),
        "unverified_examples": unverified_examples,
    }
    
    with open(verification_report, "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n=== Evidence Verification Report ===")
    print(f"Total quotes:      {total_quotes}")
    print(f"Verified:          {total_verified} ({rate:.1f}%)")
    print(f"Unverified:        {total_unverified} ({100-rate:.1f}%)")
    print(f"\nEnriched output:   {enriched_output}")
    print(f"Report saved:      {verification_report}")

if __name__ == "__main__":
    main()