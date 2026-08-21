"""
Re-extract emails whose extractions are stale (produced by an older prompt version).

Usage:
  python scripts/reextract_stale.py --dry-run    # just report what's stale
  python scripts/reextract_stale.py               # actually re-extract

After re-extraction, run run_enrichment_pipeline.py to re-enrich.
"""
import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extraction.version_manager import compute_prompt_hash, find_stale_extractions
from src.extraction.prompts import EXTRACTION_INSTRUCTIONS  
from src.extraction.extractor import extract_from_email
from src.extraction.checkpoint import load_checkpoint, save_checkpoint  # adjust

MODEL_NAME = "gemini-3.1-flash-lite"


def main():
    parser = argparse.ArgumentParser(description="Re-extract stale extractions")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only report stale count, don't re-extract")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max emails to re-extract (for testing)")
    args = parser.parse_args()
    
    base = Path(__file__).parent.parent.parent / "data" / "processed"
    
    current_hash = compute_prompt_hash(EXTRACTION_INSTRUCTIONS)
    print(f"Current prompt hash: {current_hash}")
    print(f"Model: {MODEL_NAME}\n")
    
    # Find which file to check
    input_file = base / "extractions_final.jsonl"
    if not input_file.exists():
        input_file = base / "extractions_gated.jsonl"
    if not input_file.exists():
        input_file = base / "extracted_entities.jsonl"
    
    print(f"Checking: {input_file}")
    
    # Find stale extractions
    stale_ids = find_stale_extractions(input_file, current_hash)
    
    print(f"Total stale extractions: {len(stale_ids)}")
    
    if args.dry_run:
        if stale_ids:
            print("\nFirst 10 stale message_ids:")
            for mid in stale_ids[:10]:
                print(f"  {mid}")
        return
    
    if not stale_ids:
        print("Nothing to re-extract.")
        return
    
    # Load source emails for re-extraction
    print("\nLoading source emails...")
    sources = {}
    source_file = base / "extraction_subset.jsonl"
    with open(source_file) as f:
        for line in f:
            email = json.loads(line)
            if email["message_id"] in set(stale_ids):
                sources[email["message_id"]] = email
    print(f"  Loaded {len(sources)} source emails for re-extraction")
    
    # Apply limit
    if args.limit:
        stale_ids = stale_ids[:args.limit]
        print(f"  Limited to {args.limit} emails")
    
    # Re-extract
    success = 0
    failed = 0
    results = []
    
    for i, mid in enumerate(stale_ids):
        source = sources.get(mid)
        if not source:
            print(f"  WARNING: No source for {mid}")
            failed += 1
            continue
        
        try:
            result = extract_from_email(source["body"], mid)
            results.append(result)
            success += 1
        except Exception as e:
            print(f"  FAILED {mid}: {e}")
            failed += 1
        
        if (i + 1) % 100 == 0:
            print(f"  Re-extracted {i+1}/{len(stale_ids)}")
    
    # Merge re-extracted results back into the main file
    if results:
        print(f"\nMerging {len(results)} re-extractions...")
        
        # Build lookup of new results
        new_results = {r["message_id"] if isinstance(r, dict) else r.message_id: r 
                       for r in results}
        
        # Read existing, replace stale, write back
        temp_file = base / "extractions_final.tmp.jsonl"
        replaced = 0
        
        with open(input_file) as f_in, open(temp_file, "w") as f_out:
            for line in f_in:
                record = json.loads(line)
                mid = record["message_id"]
                
                if mid in new_results:
                    # Write the new extraction (raw — needs re-enrichment)
                    new = new_results[mid]
                    if hasattr(new, "model_dump"):
                        new = new.model_dump()
                    f_out.write(json.dumps(new) + "\n")
                    replaced += 1
                else:
                    f_out.write(line)
        
        # Replace original
        temp_file.rename(input_file)
        print(f"  Replaced {replaced} extractions in {input_file.name}")
        print(f"\n  IMPORTANT: Run run_enrichment_pipeline.py to re-enrich")
    
    print(f"\nDone. Success: {success}, Failed: {failed}")


if __name__ == "__main__":
    main()