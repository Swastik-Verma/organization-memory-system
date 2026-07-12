"""
check_duplicates.py

Checks how many duplicate message_ids exist in the parsed dataset.
This is purely diagnostic — no deduplication happens yet (that's Week 3-4 work).
"""

import json
from pathlib import Path
from collections import Counter

def check_duplicates(jsonl_path: Path):
    message_ids = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            message_ids.append(record["message_id"])

    total = len(message_ids)
    unique = len(set(message_ids))
    duplicate_count = total - unique

    print(f"Total records: {total}")
    print(f"Unique message_ids: {unique}")
    print(f"Duplicate records: {duplicate_count}")
    print(f"Duplication rate: {duplicate_count / total * 100:.2f}%\n")

    # Show a few examples of the most duplicated message_ids
    counts = Counter(message_ids)
    most_common = counts.most_common(5)
    print("Top 5 most duplicated message_ids:")
    for msg_id, count in most_common:
        print(f"  {msg_id} -> appears {count} times")


if __name__ == "__main__":
    jsonl_path = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "parsed_emails.jsonl"
    check_duplicates(jsonl_path)