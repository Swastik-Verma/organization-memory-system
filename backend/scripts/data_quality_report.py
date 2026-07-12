"""
data_quality_report.py

Generates a summary report of the parsed Enron email dataset:
record counts, success rate, failure breakdown, date range, and
duplicate check. Run this after batch_parse_emails.py has produced
parsed_emails.jsonl.
"""

import json
from pathlib import Path
from datetime import datetime
from collections import Counter


def generate_report(jsonl_path: Path, total_files_attempted: int, failure_count: int):
    """
    Reads the parsed_emails.jsonl file and computes summary statistics.

    Args:
        jsonl_path: path to parsed_emails.jsonl
        total_files_attempted: total files batch_parse_emails.py tried to process
        failure_count: number of files that failed parsing (from your earlier run)
    """
    message_ids = []
    dates = []
    null_date_count = 0

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            message_ids.append(record["message_id"])

            # Dates were saved as ISO strings by model_dump_json(); some
            # records may have a null date if parsing the date failed,
            # so we skip those rather than crashing.
            if record.get("date"):
                dates.append(datetime.fromisoformat(record["date"]))
            else:
                null_date_count += 1

    total_success = len(message_ids)
    success_rate = (total_success / total_files_attempted) * 100

    unique_ids = len(set(message_ids))
    duplicate_count = total_success - unique_ids

    earliest = min(dates) if dates else None
    latest = max(dates) if dates else None

    # --- Print the report ---
    print("NOTE: X records have implausible dates (e.g. year 1979, 2044) — known source data issue, to be filtered during Week 4-5 schema refinement")
    print("=" * 50)
    print("DATA QUALITY REPORT — Enron Email Parsing Pipeline")
    print("=" * 50)
    print(f"Total files attempted:     {total_files_attempted}")
    print(f"Successfully parsed:       {total_success}")
    print(f"Failed to parse:           {failure_count}")
    print(f"Success rate:              {success_rate:.3f}%")
    print()
    print(f"Unique message_ids:        {unique_ids}")
    print(f"Duplicate records:         {duplicate_count}")
    print()
    print(f"Records with valid date:   {len(dates)}")
    print(f"Records with null date:    {null_date_count}")
    print(f"Earliest email date:       {earliest}")
    print(f"Latest email date:         {latest}")
    print("=" * 50)


if __name__ == "__main__":
    jsonl_path = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "parsed_emails.jsonl"

    # These two numbers come from yesterday's batch_parse_emails.py run.
    # We're hardcoding them here since that script doesn't currently
    # save its own counts anywhere — just plug in your real numbers.
    total_files_attempted = 517401   # 517389 success + 12 failure
    failure_count = 12

    generate_report(jsonl_path, total_files_attempted, failure_count)