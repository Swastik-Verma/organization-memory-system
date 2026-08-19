"""
select_extraction_subset.py

Selects a focused ~10,000-email subset from parsed_emails.jsonl,
concentrated around key Enron executives whose mailboxes are
well-connected and historically significant.

Writes the result to data/processed/extraction_subset.jsonl —
this is what batch_extract.py will use as its input.
"""

import sys
import json
from pathlib import Path
from collections import defaultdict

sys.path.append(str(Path(__file__).resolve().parent.parent))

# --- Configuration ---
# These are the x_origin values that appear in your parsed emails.
# x_origin corresponds to the mailbox owner (set during Enron's mail export).
# All lowercase, matches exactly what your parser stored in Day 2.
TARGET_ORIGINS = {
    "Kaminski-V",     # 26,995 emails — Head of Research, analytical/strategy
    "DASOVICH-J",     # 26,323 emails — Government affairs, regulatory work
    "KEAN-S",         # 23,621 emails — Chief of Staff to CEO, central connector
    "MANN-K",         # 22,414 emails — Legal counsel, deal/contract discussions
    "JONES-T",        # 18,598 emails — Legal, trading compliance
    "Beck-S",         #  9,056 emails — COO of Global Markets
    "NEMEC-G",        #  8,913 emails — Legal counsel, contracts
    "Arnold-J",       #  4,614 emails — Star trader
    "KITCHEN-L",      #  4,572 emails — President of Enron Online
    "LAY-K",          #  3,593 emails — Chairman/CEO
}

TOTAL_CAP = 10_000          # maximum emails in the final subset
PER_PERSON_CAP = 1_500      # max emails per person, prevents one heavy
                             # mailbox from crowding out everyone else

INPUT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "processed" / "parsed_emails.jsonl"
)
OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "processed" / "extraction_subset.jsonl"
)


def select_subset():
    print("Loading parsed emails...")

    # Group emails by x_origin first, so we can apply per-person caps
    # before assembling the final combined list.
    by_origin: dict[str, list[dict]] = defaultdict(list)
    total_loaded = 0

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            origin = record.get("x_origin", "").strip()

            # Check if this email belongs to one of our target mailboxes.
            # Case-insensitive comparison to handle any casing variations
            # in the raw data.
            for target in TARGET_ORIGINS:
                if origin.lower() == target.lower():
                    by_origin[target].append(record)
                    break

            total_loaded += 1
            if total_loaded % 50000 == 0:
                print(f"  Scanned {total_loaded} records so far...")

    print(f"\nFinished scanning {total_loaded} total records.")
    print(f"\nEmails found per target mailbox:")

    # Apply per-person cap and report counts
    selected: list[dict] = []
    for origin in sorted(TARGET_ORIGINS):
        emails = by_origin[origin]
        capped = emails[:PER_PERSON_CAP]
        selected.extend(capped)
        print(f"  {origin}: {len(emails)} found, {len(capped)} selected")

    # Apply overall total cap
    # Sort by date first so if we have to cut, we keep the
    # chronologically earliest emails (usually richer in context
    # for the scandal timeline) rather than cutting arbitrarily.
    selected.sort(key=lambda r: r.get("date") or "")
    final = selected[:TOTAL_CAP]

    print(f"\nTotal selected: {len(final)} emails")

    # Write to output file
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for record in final:
            f.write(json.dumps(record) + "\n")

    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    select_subset()