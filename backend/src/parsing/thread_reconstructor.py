import json
import re
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field

def normalize_subject(subject: str) -> str:
    """
    Strip Re:, Fw:, Fwd: prefixes and normalize whitespace
    to get the base subject for thread matching.
    
    "Re: Fw: Re: Trading desk update" → "trading desk update"
    """
    if not subject:
        return ""
    # Remove Re:/Fw:/Fwd: prefixes (can be nested)
    cleaned = re.sub(r'^(Re|Fw|Fwd)\s*:\s*', '', subject, flags=re.IGNORECASE)
    # Recurse until no more prefixes
    while cleaned != subject:
        subject = cleaned
        cleaned = re.sub(r'^(Re|Fw|Fwd)\s*:\s*', '', subject, flags=re.IGNORECASE)
    return cleaned.strip().lower()


def build_threads(parsed_emails_path: Path) -> dict[str, list[str]]:
    """
    Group emails into threads. First tries In-Reply-To/References
    headers. If those are missing (common in packaged Enron dataset),
    falls back to subject-line matching.
    """

    emails = []
    has_reply_headers = False

    with open(parsed_emails_path, 'r', encoding='utf-8') as f:
        for line in f:
            email = json.loads(line)
            mid = email.get('message_id')
            if not mid:
                continue
            emails.append(email)
            if email.get('in_reply_to') or email.get('references'):
                has_reply_headers = True

    if has_reply_headers:
        print("Using In-Reply-To/References headers for threading...")
        return _build_threads_from_headers(emails)
    else:
        print("No reply headers found — falling back to subject-line threading...")
        return _build_threads_from_subjects(emails)


def _build_threads_from_headers(emails: list[dict]) -> dict[str, list[str]]:
    """Thread using In-Reply-To and References headers."""
    parent_map = {}
    emails_by_id = {}

    for email in emails:
        mid = email['message_id']
        emails_by_id[mid] = email

        in_reply_to = email.get('in_reply_to')
        if in_reply_to:
            parent_map[mid] = in_reply_to.strip()
        elif email.get('references'):
            refs = email['references']
            if refs:
                parent_map[mid] = refs[-1].strip()

    def find_root(mid: str) -> str:
        visited = set()
        current = mid
        while current in parent_map:
            if current in visited:
                break
            visited.add(current)
            current = parent_map[current]
        return current

    thread_groups = defaultdict(list)
    for mid in emails_by_id:
        root = find_root(mid)
        thread_groups[root].append(mid)

    threads = {}
    for root_id, member_ids in thread_groups.items():
        sorted_ids = sorted(
            member_ids,
            key=lambda mid: emails_by_id[mid].get('date') or '9999'
        )
        threads[root_id] = sorted_ids

    return threads


def _build_threads_from_subjects(emails: list[dict]) -> dict[str, list[str]]:
    """
    Thread using subject line matching. Emails with the same
    normalized subject (after stripping Re:/Fw: prefixes) are
    grouped into one thread.
    """
    subject_groups = defaultdict(list)

    for email in emails:
        mid = email.get('message_id')
        subject = email.get('subject', '')
        base_subject = normalize_subject(subject)

        # Skip empty subjects — they'd all merge into one giant thread
        if not base_subject:
            subject_groups[mid] = [mid]  # standalone thread
            continue

        subject_groups[base_subject].append({
            'message_id': mid,
            'date': email.get('date') or '9999',
        })

    threads = {}
    for key, members in subject_groups.items():
        if isinstance(members, list) and len(members) > 0:
            if isinstance(members[0], dict):
                # Sort by date
                sorted_members = sorted(members, key=lambda m: m['date'])
                root_id = sorted_members[0]['message_id']
                threads[root_id] = [m['message_id'] for m in sorted_members]
            else:
                # Standalone thread (empty subject)
                threads[key] = members

    return threads


def save_threads(threads: dict[str, list[str]], output_path: Path):
    """Save thread map to JSON."""
    output = {
        'total_threads': len(threads),
        'single_message_threads': sum(1 for v in threads.values() if len(v) == 1),
        'multi_message_threads': sum(1 for v in threads.values() if len(v) > 1),
        'largest_thread_size': max(len(v) for v in threads.values()) if threads else 0,
        'threads': threads,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)

    print(f"Total threads:           {output['total_threads']}")
    print(f"Single-message threads:  {output['single_message_threads']}")
    print(f"Multi-message threads:   {output['multi_message_threads']}")
    print(f"Largest thread:          {output['largest_thread_size']} messages")


if __name__ == '__main__':
    BASE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "processed"
    parsed_path = BASE / "parsed_emails.jsonl"
    output_path = BASE / "threads.json"

    print("Building threads from parsed emails...")
    threads = build_threads(parsed_path)
    save_threads(threads, output_path)
    print(f"Saved to {output_path}")