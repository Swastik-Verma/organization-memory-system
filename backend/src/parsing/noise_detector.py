"""
noise_detector.py

Detects quoted reply blocks, forwarding headers, and signature
footers in email bodies. Returns the byte ranges of each region
so downstream code can check whether an evidence quote falls
inside original content or inside noise.

Does NOT modify the body — it's a detector, not a stripper,
because extraction already happened on the raw bodies.
"""

import re
from dataclasses import dataclass


@dataclass
class NoiseRegion:
    """A region of the email body that is not original content."""
    start: int          # character offset in the body
    end: int            # character offset in the body
    region_type: str    # "quoted_reply", "forward_header", or "signature"


# Patterns for forwarding headers — these appear as a block before
# the forwarded content begins
FORWARD_PATTERNS = [
    re.compile(r'-{3,}\s*Original Message\s*-{3,}', re.IGNORECASE),
    re.compile(r'-{3,}\s*Forwarded by\s+.+?-{3,}', re.DOTALL),
    re.compile(r'Begin forwarded message:', re.IGNORECASE),
]

# Pattern for the start of a quoted reply block
# Matches lines starting with ">" or lines like "On Mar 4, John wrote:"
QUOTE_LINE_PATTERN = re.compile(r'^>', re.MULTILINE)
WROTE_PATTERN = re.compile(
    r'^.*(?:wrote|writes|said|sent):\s*$', re.IGNORECASE | re.MULTILINE
)

# Signature delimiters
# Standard delimiter is "-- " (dash dash space) on its own line
# Also catch common patterns like just "--" or "___"
SIGNATURE_PATTERNS = [
    re.compile(r'^-- ?\s*$', re.MULTILINE),        # standard "-- "
    re.compile(r'^_{3,}\s*$', re.MULTILINE),        # "___..."
    re.compile(r'^-{3,}\s*$', re.MULTILINE),        # "---..."
    re.compile(r'^\*{3,}\s*$', re.MULTILINE),       # "***..."
]


def detect_noise_regions(body: str) -> list[NoiseRegion]:
    """
    Scan an email body and return a list of NoiseRegion objects
    identifying non-original content.

    Args:
        body: the full email body text

    Returns:
        list of NoiseRegion with start/end offsets and type
    """
    if not body:
        return []

    regions = []

    # --- Forwarding headers ---
    # Everything from the forward marker to the end of the body
    # is forwarded content
    for pattern in FORWARD_PATTERNS:
        match = pattern.search(body)
        if match:
            regions.append(NoiseRegion(
                start=match.start(),
                end=len(body),
                region_type="forward_header"
            ))

    # --- Quoted reply blocks ---
    # Find consecutive lines starting with ">"
    # Also find "On ... wrote:" lines that introduce a quote block
    lines = body.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for "wrote:" introducer
        if WROTE_PATTERN.match(line):
            # Find the start offset of this line in the body
            block_start = sum(len(l) + 1 for l in lines[:i])

            # Everything from here to end is typically quoted
            # But stop if we hit original content again (lines not starting with >)
            j = i + 1
            while j < len(lines) and (
                lines[j].startswith('>') or lines[j].strip() == ''
            ):
                j += 1

            block_end = sum(len(l) + 1 for l in lines[:j])
            regions.append(NoiseRegion(
                start=block_start,
                end=min(block_end, len(body)),
                region_type="quoted_reply"
            ))
            i = j
            continue

        # Check for standalone ">" quoted lines (no "wrote:" introducer)
        if line.startswith('>'):
            block_start = sum(len(l) + 1 for l in lines[:i])
            j = i
            while j < len(lines) and (
                lines[j].startswith('>') or lines[j].strip() == ''
            ):
                j += 1
            block_end = sum(len(l) + 1 for l in lines[:j])
            regions.append(NoiseRegion(
                start=block_start,
                end=min(block_end, len(body)),
                region_type="quoted_reply"
            ))
            i = j
            continue

        i += 1

    # --- Signature blocks ---
    # Find the LAST signature delimiter — everything after it is signature
    last_sig_start = None
    for pattern in SIGNATURE_PATTERNS:
        for match in pattern.finditer(body):
            # Only consider it a signature if it's in the bottom half
            # of the email — a "---" in the first paragraph is likely
            # a section divider, not a signature
            if match.start() > len(body) * 0.5:
                if last_sig_start is None or match.start() > last_sig_start:
                    last_sig_start = match.start()

    if last_sig_start is not None:
        regions.append(NoiseRegion(
            start=last_sig_start,
            end=len(body),
            region_type="signature"
        ))

    return regions


def is_in_noise(char_start: int, char_end: int,
                regions: list[NoiseRegion]) -> bool:
    """
    Check whether a text span (e.g. an evidence quote) falls
    inside any noise region.

    Returns True if the span overlaps with any noise region.
    """
    for region in regions:
        # Check for any overlap between the span and the region
        if char_start < region.end and char_end > region.start:
            return True
    return False


def get_original_content(body: str,
                         regions: list[NoiseRegion]) -> str:
    """
    Return only the original (non-noise) portions of the body,
    concatenated. Useful for display or analysis but NOT used
    to modify the stored body — raw data stays immutable.
    """
    if not regions:
        return body

    # Sort regions by start position
    sorted_regions = sorted(regions, key=lambda r: r.start)

    original_parts = []
    cursor = 0
    for region in sorted_regions:
        if cursor < region.start:
            original_parts.append(body[cursor:region.start])
        cursor = max(cursor, region.end)
    if cursor < len(body):
        original_parts.append(body[cursor:])

    return '\n'.join(part.strip() for part in original_parts if part.strip())