"""
review_noise_detection.py

Displays email bodies alongside their detected noise regions
for manual quality review. Shows 20 random emails.

Usage:
    python scripts/review_noise_detection.py
"""

import json
import random
from pathlib import Path
from src.parsing.noise_detector import detect_noise_regions

BASE = Path(__file__).resolve().parent.parent.parent / "data" / "processed"
SUBSET_PATH = BASE / "extraction_subset.jsonl"


def review():
    with open(SUBSET_PATH, 'r', encoding='utf-8') as f:
        emails = [json.loads(line) for line in f]

    # Pick 20 random emails that have some body content
    candidates = [e for e in emails if len(e.get('body', '')) > 100]
    sample = random.sample(candidates, min(20, len(candidates)))

    for i, email in enumerate(sample, 1):
        body = email.get('body', '')
        regions = detect_noise_regions(body)

        print(f"\n{'='*60}")
        print(f"EMAIL {i}/20")
        print(f"From:    {email.get('from_addr', 'unknown')}")
        print(f"Subject: {email.get('subject', 'no subject')}")
        print(f"Date:    {email.get('date', 'no date')}")
        print(f"Body length: {len(body)} chars")
        print(f"Noise regions found: {len(regions)}")

        if regions:
            for r in regions:
                print(f"  [{r.region_type}] chars {r.start}-{r.end}")
                # Show a preview of the noise region
                preview = body[r.start:min(r.end, r.start + 200)]
                print(f"  Preview: {preview[:200]}...")
        else:
            print("  No noise detected")

        print(f"\n--- ORIGINAL CONTENT (first 500 chars) ---")
        from src.parsing.noise_detector import get_original_content
        original = get_original_content(body, regions)
        print(original[:500])

        print(f"\n--- FULL BODY (first 500 chars) ---")
        print(body[:500])

        print(f"\n[Press Enter for next, 'q' to quit]")
        user = input()
        if user.lower() == 'q':
            break


if __name__ == '__main__':
    review()