"""
Extraction versioning — tracks which prompt and model produced each extraction.
Identifies stale extractions that need re-running when the prompt changes.
"""
import hashlib
import json
from pathlib import Path


def compute_prompt_hash(prompt_text: str) -> str:
    """
    Compute a short deterministic hash of the prompt text.
    Same prompt → same hash. Any change → different hash.
    """
    return hashlib.sha256(prompt_text.encode()).hexdigest()[:12]


def get_current_version(prompt_text: str, model_name: str) -> dict:
    """Return the current extraction version info."""
    return {
        "prompt_version": compute_prompt_hash(prompt_text),
        "model_name": model_name,
    }


def stamp_extraction(extraction: dict, prompt_text: str, model_name: str) -> dict:
    """Add version stamps to an extraction result."""
    extraction["prompt_version"] = compute_prompt_hash(prompt_text)
    extraction["model_name"] = model_name
    return extraction


def find_stale_extractions(extractions_path: Path, 
                           current_prompt_hash: str) -> list[str]:
    """
    Find message_ids of extractions produced by an older prompt version.
    
    Returns a list of message_ids that need re-extraction.
    """
    stale_ids = []
    with open(extractions_path) as f:
        for line in f:
            record = json.loads(line)
            if record.get("prompt_version", "") != current_prompt_hash:
                stale_ids.append(record["message_id"])
    return stale_ids


def version_report(extractions_path: Path) -> dict:
    """
    Generate a report of which versions are present in the extractions file.
    
    Returns:
        {
            "total": int,
            "by_version": {
                "prompt_hash:model_name": count,
                ...
            },
            "unstamped": int  (extractions with no version info)
        }
    """
    from collections import Counter
    version_counts = Counter()
    unstamped = 0
    total = 0
    
    with open(extractions_path) as f:
        for line in f:
            total += 1
            record = json.loads(line)
            prompt_v = record.get("prompt_version", "")
            model = record.get("model_name", "")
            
            if not prompt_v:
                unstamped += 1
            else:
                key = f"{prompt_v}:{model}"
                version_counts[key] += 1
    
    return {
        "total": total,
        "by_version": dict(version_counts),
        "unstamped": unstamped,
    }