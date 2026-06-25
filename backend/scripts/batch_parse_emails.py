"""
batch_parse_emails.py

Walks through raw Enron email files, parses and validates each one,
and reports successes/failures. This is a diagnostic/test run for now —
saving to disk comes in a later step.
"""

import sys
from pathlib import Path

# Allow this script to import from src/, since scripts/ and src/ are siblings
# under backend/. Without this, Python wouldn't know where to find
# 'src.parsing.email_parser' when running this file directly.
sys.path.append(str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError
from src.parsing.email_parser import parse_email_file
from src.parsing.schema import ParsedEmail


def find_email_files(raw_dir: Path, limit: int = None) -> list[Path]:
    """
    Recursively finds all email files under raw_dir.

    Enron email files have no file extension (e.g. just '1.', '2.'),
    so instead of filtering by extension, we treat every file
    (not directory) as a candidate email.

    Args:
        raw_dir: root folder to search
        limit: optional cap on number of files returned (for testing)
    """
    all_files = [p for p in raw_dir.rglob("*") if p.is_file()]
    if limit:
        return all_files[:limit]
    return all_files


def batch_parse(raw_dir: Path, limit: int = None):
    """
    Parses every email file found under raw_dir, validates each one
    against the ParsedEmail schema, and reports results.
    """
    files = find_email_files(raw_dir, limit=limit)
    print(f"Found {len(files)} files to process.\n")

    successes: list[ParsedEmail] = []
    failures: list[dict] = []

    for file_path in files:
        print(f"Processing: {file_path}")
        try:
            raw_dict = parse_email_file(str(file_path))
            parsed = ParsedEmail(**raw_dict)
            successes.append(parsed)
        except ValidationError as e:
            # The file was read fine, but its contents didn't match
            # our required schema (e.g. missing message_id or body).
            failures.append({"file": str(file_path), "error": str(e)})
        except Exception as e:
            # Catches anything unexpected — e.g. a corrupted file that
            # the email module itself couldn't even read.
            failures.append({"file": str(file_path), "error": f"Unexpected error: {e}"})

    print(f"Successfully parsed: {len(successes)}")
    print(f"Failed: {len(failures)}\n")

    if failures:
        print("--- Failure details ---")
        for f in failures:
            print(f"File: {f['file']}")
            print(f"Error: {f['error']}\n")

    return successes, failures


import json

def save_to_jsonl(parsed_emails: list[ParsedEmail], output_path: Path):
    """
    Saves a list of ParsedEmail objects to a JSON Lines file —
    one JSON object per line.

    Args:
        parsed_emails: list of validated ParsedEmail objects
        output_path: where to write the .jsonl file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for email in parsed_emails:
            # model_dump_json() is Pydantic's built-in method to convert
            # a model into a JSON string. It correctly handles the
            # datetime field for us (converts to ISO format automatically).
            f.write(email.model_dump_json() + "\n")

    print(f"Saved {len(parsed_emails)} emails to {output_path}")




if __name__ == "__main__":
    raw_dir = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "maildir"
    processed_dir = Path(__file__).resolve().parent.parent.parent / "data" / "processed"

    successes, failures = batch_parse(raw_dir, limit=20)

    if successes:
        save_to_jsonl(successes, processed_dir / "parsed_emails_test.jsonl")