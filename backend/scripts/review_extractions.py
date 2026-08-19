"""
review_extractions.py

Prints each extraction result alongside its source email, so you can
manually verify extraction quality against the original text.
"""

import sys
import json
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

BASE = Path(__file__).resolve().parent.parent.parent / "data" / "processed"
SUBSET_PATH = BASE / "extraction_subset.jsonl"
EXTRACTED_PATH = BASE / "extracted_entities.jsonl"


def review(start: int = 0, count: int = 5):
    # Load source emails into a lookup by message_id
    sources = {}
    with open(SUBSET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            sources[r["message_id"]] = r

    # Load extractions
    extractions = []
    with open(EXTRACTED_PATH, "r", encoding="utf-8") as f:
        for line in f:
            extractions.append(json.loads(line))

    print(f"Total extractions available: {len(extractions)}\n")

    for result in extractions[start:start + count]:
        src = sources.get(result["message_id"], {})

        print("=" * 70)
        print(f"MESSAGE ID: {result['message_id']}")
        print(f"FROM: {src.get('from_addr')}")
        print(f"TO: {src.get('to_addrs')}")
        print(f"SUBJECT: {src.get('subject')}")
        print("-" * 70)
        print("BODY:")
        body = src.get("body", "")
        print(body[:1500])          # cap very long bodies for readability
        if len(body) > 1500:
            print(f"... [truncated, {len(body)} chars total]")
        print("-" * 70)
        print("EXTRACTED:")
        print(json.dumps(
            {k: v for k, v in result.items() if k != "message_id"},
            indent=2
        ))
        print("=" * 70)
        print()


if __name__ == "__main__":
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    review(start, count)