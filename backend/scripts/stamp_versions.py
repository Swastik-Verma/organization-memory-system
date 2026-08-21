"""
Retroactively stamp existing extractions with prompt version and model name.
Also works for future re-stamping when the scored file needs updating.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.extraction.version_manager import compute_prompt_hash
from src.extraction.prompts import EXTRACTION_INSTRUCTIONS # adjust import to match your actual prompt variable name


# The model used for the existing 10k extraction
MODEL_NAME = "gemini-3.1-flash-lite"


def main():
    base = Path(__file__).parent.parent.parent / "data" / "processed"
    
    # Compute current prompt hash
    prompt_hash = compute_prompt_hash(EXTRACTION_INSTRUCTIONS)
    print(f"Prompt hash: {prompt_hash}")
    print(f"Model name:  {MODEL_NAME}")
    
    # Determine which file to stamp
    # Use the most enriched version (scored > with_offsets > raw)
    input_candidates = [
        "extractions_scored.jsonl",
        "extractions_with_offsets.jsonl",
        "extracted_entities.jsonl",
    ]
    
    input_file = None
    for candidate in input_candidates:
        path = base / candidate
        if path.exists():
            input_file = path
            print(f"\nStamping: {input_file}")
            break
    
    if not input_file:
        print("ERROR: No extractions file found")
        return
    
    # Read, stamp, write back
    output_file = base / "extractions_versioned.jsonl"
    count = 0
    already_stamped = 0
    
    with open(input_file) as f_in, open(output_file, "w") as f_out:
        for line in f_in:
            record = json.loads(line)
            
            if record.get("prompt_version") == prompt_hash:
                already_stamped += 1
            
            record["prompt_version"] = prompt_hash
            record["model_name"] = MODEL_NAME
            
            f_out.write(json.dumps(record) + "\n")
            count += 1
    
    print(f"Stamped {count} extractions")
    if already_stamped:
        print(f"  ({already_stamped} were already stamped with this version)")
    print(f"Output: {output_file}")


if __name__ == "__main__":
    main()