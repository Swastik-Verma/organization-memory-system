"""
batch_extract.py

Runs Gemini extraction across parsed_emails.jsonl, respecting free-tier
rate limits and a daily request cap. Safe to re-run every day — it
automatically skips already-completed emails via checkpoint.py and
picks up exactly where the previous run left off.
"""

import sys
import json
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.extraction.extractor import extract_from_email, ExtractionError
from src.extraction.checkpoint import Checkpoint

# --- Configuration ---
# Kept as named constants at the top so they're easy to find and tune
# without hunting through the script's logic.
DAILY_LIMIT = 10000          # safety buffer under the real 1,500 RPD cap
SECONDS_BETWEEN_CALLS = 0.5   # ~8.5 requests/minute, safety buffer under 10 RPM
RATE_LIMIT_BACKOFF = 60     # if we DO get a 429, wait this long before retrying

INPUT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "extraction_subset.jsonl"
OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "extracted_entities.jsonl"
CHECKPOINT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "extraction_checkpoint.json"


def load_all_records(path: Path) -> list[dict]:
    """Loads every parsed email record from the JSONL file into memory.
    At ~517k records this is a few hundred MB at most — well within
    an 8GB machine's limits, and simpler than streaming line-by-line
    for this use case."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    return records


def append_result(result, output_path: Path):
    """Appends one extraction result to the output file.
    Using append mode ('a') rather than rewriting the whole file each
    time — same reasoning as checkpoint.py: crash-safety and speed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(result.model_dump_json() + "\n")


def run_batch_extraction():
    checkpoint = Checkpoint(CHECKPOINT_PATH)
    all_records = load_all_records(INPUT_PATH)

    print(f"Total emails in dataset: {len(all_records)}")
    print(f"Already completed (from checkpoint): {checkpoint.progress_count()}")

    processed_today = 0
    failures_today = 0

    max_retries = 3
    
    for record in all_records:
        message_id = record["message_id"]

        if checkpoint.is_done(message_id):
            continue

        if processed_today >= DAILY_LIMIT:
            print(f"\nReached daily limit of {DAILY_LIMIT}. Stopping for today.")
            break

        # Try up to max_retries times for temporary errors (429/503),
        # then skip this email (without marking done) and move on.
        succeeded = False
        for attempt in range(1, max_retries + 1):
            try:
                result = extract_from_email(record)
                append_result(result, OUTPUT_PATH)
                checkpoint.mark_done(message_id)
                processed_today += 1
                succeeded = True

                if processed_today % 100 == 0:
                    print(f"  {processed_today} processed today "
                          f"({checkpoint.progress_count()} total complete)")
                break  # exit retry loop on success

            except ExtractionError as e:
                error_str = str(e)
                print(e)

                if "429" in error_str or "503" in error_str or "disconnected" in error_str.lower() or "timeout" in error_str.lower():
                    print(f"  Temporary error (attempt {attempt}/{max_retries}) "
                          f"— pausing {RATE_LIMIT_BACKOFF}s...")
                    time.sleep(RATE_LIMIT_BACKOFF)
                    # loop continues to next attempt automatically
                else:
                    # Permanent failure — mark done so we don't retry forever
                    print(f"  FAILED (permanent): {message_id} -> {e}")
                    failures_today += 1
                    checkpoint.mark_done(message_id)
                    break  # exit retry loop

        if not succeeded and not checkpoint.is_done(message_id):
            # All retry attempts exhausted on a temporary error.
            # Do NOT mark as done — next daily run will try again
            # when the server is hopefully recovered.
            print(f"  Skipping after {max_retries} failed attempts: {message_id}")
            failures_today += 1

        time.sleep(SECONDS_BETWEEN_CALLS)

    print(f"\n--- Today's run summary ---")
    print(f"Processed successfully: {processed_today}")
    print(f"Failed: {failures_today}")
    print(f"Total completed overall: {checkpoint.progress_count()} / {len(all_records)}")


if __name__ == "__main__":
    run_batch_extraction()