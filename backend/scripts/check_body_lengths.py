"""
check_body_lengths.py

Check body length distribution to verify whether chunking is needed.
If P99 is well under Gemini's context limit, chunking is unnecessary.
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent / "data" / "processed"
SUBSET_PATH = BASE / "extraction_subset.jsonl"


def check():
    lengths = []
    with open(SUBSET_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            email = json.loads(line)
            body = email.get('body', '')
            lengths.append(len(body))

    lengths.sort()
    n = len(lengths)

    print(f"Total emails:    {n}")
    print(f"Min body length: {lengths[0]} chars")
    print(f"P50 (median):    {lengths[n // 2]} chars")
    print(f"P90:             {lengths[int(n * 0.9)]} chars")
    print(f"P95:             {lengths[int(n * 0.95)]} chars")
    print(f"P99:             {lengths[int(n * 0.99)]} chars")
    print(f"Max body length: {lengths[-1]} chars")
    print()

    # Rough token estimate: 1 token ≈ 4 characters
    max_tokens_approx = lengths[-1] // 4
    p99_tokens_approx = lengths[int(n * 0.99)] // 4
    print(f"P99 tokens (approx):  {p99_tokens_approx}")
    print(f"Max tokens (approx):  {max_tokens_approx}")
    print()

    # Gemini flash-lite context window is large (>100k tokens)
    # If max is under 30k tokens, chunking is clearly unnecessary
    if max_tokens_approx < 30000:
        print("CONCLUSION: Chunking is NOT needed.")
        print("Even the longest email fits comfortably in the context window.")
    else:
        print(f"WARNING: {sum(1 for l in lengths if l // 4 > 30000)} emails exceed 30k tokens.")
        print("Consider chunking those specific emails.")


if __name__ == '__main__':
    check()