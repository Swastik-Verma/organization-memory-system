"""
Verify extraction evidence quotes against source email bodies.
Compute character offsets for verified quotes.
Flag unverifiable quotes as potential hallucinations.
"""
import re
import json
from pathlib import Path


def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace (newlines, tabs, multiple spaces) into single spaces."""
    return re.sub(r'\s+', ' ', text).strip()


def build_offset_map(original: str) -> list[int]:
    """
    Build a mapping from positions in the normalized string
    back to positions in the original string.
    
    Returns a list where offset_map[normalized_pos] = original_pos.
    This lets us convert a match position in the normalized string
    back to the correct character offset in the raw email body.
    """
    offset_map = []
    i = 0
    in_whitespace = False
    
    for orig_pos, char in enumerate(original):
        if char in ' \t\n\r':
            if not in_whitespace:
                # First whitespace char in a run → maps to the single space
                offset_map.append(orig_pos)
                in_whitespace = True
            # Subsequent whitespace chars in the run → skip (they collapse)
        else:
            offset_map.append(orig_pos)
            in_whitespace = False
    
    return offset_map



def collapse_whitespace(text: str) -> str:
    """Collapse whitespace runs to single spaces but do NOT strip."""
    return re.sub(r'\s+', ' ', text)

def find_quote_in_body(quote: str, body: str) -> tuple[int, int] | None:
    if not quote or not body:
        return None

    norm_quote = normalize_whitespace(quote)   # strip + collapse (fine for quote)
    collapsed_body = collapse_whitespace(body)  # collapse only, no strip

    pos = collapsed_body.find(norm_quote)
    if pos == -1:
        pos = collapsed_body.lower().find(norm_quote.lower())
    if pos == -1:
        return None

    offset_map = build_offset_map(body)  # built from original

    if pos >= len(offset_map) or (pos + len(norm_quote) - 1) >= len(offset_map):
        return None

    char_start = offset_map[pos]
    char_end = offset_map[pos + len(norm_quote) - 1]
    return (char_start, char_end)


def verify_extraction(extraction: dict, source_email: dict) -> dict:
    """
    Verify all evidence quotes in an extraction against its source email body.
    
    Returns a verification report:
    {
        "message_id": str,
        "total_quotes": int,
        "verified": int,
        "unverified": int,
        "details": [
            {
                "field": "people" | "relationships" | ...,
                "index": int,
                "quote": str,
                "char_start": int | None,
                "char_end": int | None,
                "verified": bool
            }
        ]
    }
    """
    body = source_email.get("body", "")
    message_id = extraction.get("message_id", "")
    details = []
    
    # Collect all evidence quotes from every extraction field
    evidence_sources = []
    
    # People
    for i, person in enumerate(extraction.get("people", [])):
        ev = person.get("evidence", "")
        if ev:
            evidence_sources.append(("people", i, ev))
    
    # Organizations
    for i, org in enumerate(extraction.get("organizations", [])):
        ev = org.get("evidence", "")
        if ev:
            evidence_sources.append(("organizations", i, ev))
    
    # Deals
    for i, deal in enumerate(extraction.get("deals", [])):
        ev = deal.get("evidence", "")
        if ev:
            evidence_sources.append(("deals", i, ev))
    
    # Decisions
    for i, dec in enumerate(extraction.get("decisions", [])):
        ev = dec.get("evidence", "")
        if ev:
            evidence_sources.append(("decisions", i, ev))
    
    # Relationships
    for i, rel in enumerate(extraction.get("relationships", [])):
        ev = rel.get("evidence", "")
        if ev:
            evidence_sources.append(("relationships", i, ev))
    
    verified_count = 0
    for field, idx, quote in evidence_sources:
        result = find_quote_in_body(quote, body)
        if result:
            char_start, char_end = result
            verified = True
            verified_count += 1
        else:
            char_start, char_end = None, None
            verified = False
        
        details.append({
            "field": field,
            "index": idx,
            "quote": quote,
            "char_start": char_start,
            "char_end": char_end,
            "verified": verified,
        })
    
    total = len(details)
    return {
        "message_id": message_id,
        "total_quotes": total,
        "verified": verified_count,
        "unverified": total - verified_count,
        "details": details,
    }