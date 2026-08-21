"""
Deterministic confidence scoring for extracted claims.

Scores are computed from verifiable signals, not LLM self-assessment.
Each claim starts at 1.0 and receives penalties for weakness indicators.

Signals:
- Evidence verification (Day 8): did the quote match the source body?
- Quote length: very short quotes are weaker evidence
- Noise region: evidence from forwarded/quoted blocks is weaker
- Entity completeness: missing email addresses, missing relationship endpoints
"""
import json
from pathlib import Path
from src.parsing.noise_detector import detect_noise_regions, is_in_noise


# --- Penalty constants ---
PENALTY_EVIDENCE_UNVERIFIED = 0.30
PENALTY_EVIDENCE_EMPTY = 0.50
PENALTY_QUOTE_VERY_SHORT = 0.15  # < 20 chars
PENALTY_QUOTE_SHORT = 0.05       # 20-40 chars
PENALTY_IN_NOISE_REGION = 0.10
PENALTY_NO_EMAIL = 0.05
PENALTY_MISSING_ENDPOINT = 0.20

CONFIDENCE_FLOOR = 0.05

# Fields that were designed to have evidence quotes in the v2 prompt
EVIDENCE_FIELDS = {"relationships"}

def score_evidence(item: dict, noise_regions: list[dict] | None = None, 
                   field_type: str = "") -> dict:
    score = 1.0
    penalties = []
    
    evidence = item.get("evidence", "")
    verified = item.get("evidence_verified")
    char_start = item.get("char_start")
    char_end = item.get("char_end")
    
    # --- Evidence quality (only for fields that should have evidence) ---
    if field_type in EVIDENCE_FIELDS:
        if not evidence or evidence.strip() == "":
            score -= PENALTY_EVIDENCE_EMPTY
            penalties.append(("empty_evidence", PENALTY_EVIDENCE_EMPTY))
        elif verified is False:
            score -= PENALTY_EVIDENCE_UNVERIFIED
            penalties.append(("unverified_evidence", PENALTY_EVIDENCE_UNVERIFIED))
        
        # Quote length (only meaningful if evidence expected)
        if evidence:
            quote_len = len(evidence.strip())
            if quote_len < 20:
                score -= PENALTY_QUOTE_VERY_SHORT
                penalties.append(("very_short_quote", PENALTY_QUOTE_VERY_SHORT))
            elif quote_len < 40:
                score -= PENALTY_QUOTE_SHORT
                penalties.append(("short_quote", PENALTY_QUOTE_SHORT))
        
        # Noise region (only meaningful if we have offsets)
        if (noise_regions is not None 
                and char_start is not None 
                and char_end is not None):
            if is_in_noise(char_start, char_end, noise_regions):
                score -= PENALTY_IN_NOISE_REGION
                penalties.append(("in_noise_region", PENALTY_IN_NOISE_REGION))
    
    # --- Entity completeness (applies to all field types) ---
    if "email" in item and not item.get("email"):
        score -= PENALTY_NO_EMAIL
        penalties.append(("no_email", PENALTY_NO_EMAIL))
    
    if "source" in item or "target" in item:
        if not item.get("source") or not item.get("target"):
            score -= PENALTY_MISSING_ENDPOINT
            penalties.append(("missing_endpoint", PENALTY_MISSING_ENDPOINT))
    
    # --- Field-specific baseline adjustments ---
    # People/orgs/deals/decisions have no evidence to verify,
    # so we can't be as confident in them as in fully-evidenced claims.
    # Apply a mild baseline penalty reflecting this inherent uncertainty.
    if field_type not in EVIDENCE_FIELDS:
        PENALTY_NO_EVIDENCE_AVAILABLE = 0.10
        score -= PENALTY_NO_EVIDENCE_AVAILABLE
        penalties.append(("no_evidence_available", PENALTY_NO_EVIDENCE_AVAILABLE))
    
    score = max(score, CONFIDENCE_FLOOR)
    
    return {
        "confidence": round(score, 2),
        "penalties": penalties,
    }


def score_extraction(extraction: dict, source_email: dict) -> dict:
    body = source_email.get("body", "")
    noise_regions = detect_noise_regions(body) if body else []
    
    for field in ["people", "organizations", "deals", "decisions", "relationships"]:
        for item in extraction.get(field, []):
            result = score_evidence(item, noise_regions, field_type=field)
            item["confidence"] = result["confidence"]
            item["confidence_penalties"] = result["penalties"]
    
    return extraction