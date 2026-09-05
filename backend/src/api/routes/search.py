"""
Global search route — unified search across all node types.

GET /api/search — search Person, Organization, Deal, Decision, Claim, Evidence
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_neo4j_driver
from src.api.models import (
    GlobalSearchResponse,
    SearchResultGroup,
    SearchResultItem,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Display labels for each type
TYPE_LABELS = {
    "person": "Persons",
    "organization": "Organizations",
    "claim": "Claims",
    "evidence": "Evidence",
    "deal": "Deals",
    "decision": "Decisions",
}

# Order in which groups appear in the response
TYPE_ORDER = ["person", "organization", "claim", "evidence", "deal", "decision"]

# Max results per type to keep response fast
PER_TYPE_LIMIT = 10


@router.get("/search", response_model=GlobalSearchResponse)
async def global_search(
    q: str = Query(..., min_length=1, description="Search query"),
    type: Optional[str] = Query(default=None, description="Filter to one type"),
    claim_type: Optional[str] = Query(default=None, description="Filter claims by type"),
    date_from: Optional[str] = Query(default=None, description="Earliest date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(default=None, description="Latest date (YYYY-MM-DD)"),
    min_confidence: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    limit: int = Query(default=10, ge=1, le=50, description="Max results per type"),
    driver=Depends(get_neo4j_driver),
):
    """
    Search across all node types in one query.

    Searches Person/Organization by canonical_name and aliases,
    Claim by description/subject_name/object_name,
    Evidence by quote text,
    Deal by name,
    Decision by description.

    Returns results grouped by type, sorted by mention_count
    (or confidence for claims/evidence).

    NOTE: counts shown per group are capped at PER_TYPE_LIMIT (10) — they
    reflect "how many are shown", not necessarily the true total number of
    matches on the server. This is a deliberate simplification for a search
    preview page, not a fully paginated results page.
    """
    per_type = min(limit, PER_TYPE_LIMIT)
    q_lower = q.strip()

    if not q_lower:
        return GlobalSearchResponse(query=q, groups=[], total_results=0)

    groups = {}

    with driver.session() as session:

        # --- Person ---
        if type is None or type == "person":
            result = session.run("""
                MATCH (p:Person)
                WHERE p.is_deleted = false
                  AND (toLower(p.canonical_name) CONTAINS toLower($q)
                       OR any(alias IN p.aliases
                              WHERE toLower(alias) CONTAINS toLower($q)
                                    AND NOT alias CONTAINS '@'))
                RETURN p.id AS id, p.canonical_name AS name,
                       p.mention_count AS mention_count
                ORDER BY p.mention_count DESC
                LIMIT $limit
            """, q=q_lower, limit=per_type)
            items = []
            for r in result:
                items.append(SearchResultItem(
                    id=r["id"], name=r["name"], type="person",
                    snippet=r["name"],
                    mention_count=r["mention_count"] or 0,
                ))
            if items:
                groups["person"] = SearchResultGroup(
                    type="person", label="Persons",
                    results=items, count=len(items),
                )

        # --- Organization ---
        if type is None or type == "organization":
            result = session.run("""
                MATCH (o:Organization)
                WHERE o.is_deleted = false
                  AND (toLower(o.canonical_name) CONTAINS toLower($q)
                       OR any(alias IN o.aliases
                              WHERE toLower(alias) CONTAINS toLower($q)))
                RETURN o.id AS id, o.canonical_name AS name,
                       o.mention_count AS mention_count
                ORDER BY o.mention_count DESC
                LIMIT $limit
            """, q=q_lower, limit=per_type)
            items = []
            for r in result:
                items.append(SearchResultItem(
                    id=r["id"], name=r["name"], type="organization",
                    snippet=r["name"],
                    mention_count=r["mention_count"] or 0,
                ))
            if items:
                groups["organization"] = SearchResultGroup(
                    type="organization", label="Organizations",
                    results=items, count=len(items),
                )

        # --- Claim ---
        if type is None or type == "claim":
            # Build dynamic WHERE clause for optional filters
            claim_filters = [
                "c.is_deleted = false",
                "(toLower(c.description) CONTAINS toLower($q)"
                " OR toLower(c.subject_name) CONTAINS toLower($q)"
                " OR toLower(c.object_name) CONTAINS toLower($q))",
            ]
            params = {"q": q_lower, "limit": per_type}

            if claim_type:
                claim_filters.append("c.claim_type = $claim_type")
                params["claim_type"] = claim_type
            if date_from:
                claim_filters.append("c.valid_from >= $date_from")
                params["date_from"] = date_from
            if date_to:
                claim_filters.append("c.valid_from <= $date_to")
                params["date_to"] = date_to
            if min_confidence is not None:
                claim_filters.append("c.confidence >= $min_confidence")
                params["min_confidence"] = min_confidence

            where_clause = " AND ".join(claim_filters)
            query = f"""
                MATCH (c:Claim)
                WHERE {where_clause}
                RETURN c.id AS id, c.description AS description,
                       c.subject_id AS subject_id,
                       c.subject_name AS subject_name,
                       c.object_name AS object_name,
                       c.claim_type AS claim_type,
                       c.confidence AS confidence,
                       c.valid_from AS valid_from,
                       c.mention_count AS mention_count
                ORDER BY c.mention_count DESC, c.confidence DESC
                LIMIT $limit
            """
            result = session.run(query, **params)
            items = []
            for r in result:
                items.append(SearchResultItem(
                    id=r["id"],
                    name=r["description"] or f"{r['subject_name']} {r['claim_type']} {r['object_name']}",
                    type="claim",
                    snippet=r["description"] or "",
                    mention_count=r["mention_count"] or 0,
                    confidence=r["confidence"],
                    date=r["valid_from"],
                    subject_id=r["subject_id"],
                ))
            if items:
                groups["claim"] = SearchResultGroup(
                    type="claim", label="Claims",
                    results=items, count=len(items),
                )

        # --- Evidence ---
        if type is None or type == "evidence":
            ev_filters = [
                "e.is_deleted = false",
                "toLower(e.quote) CONTAINS toLower($q)",
            ]
            params = {"q": q_lower, "limit": per_type}

            # FIX: date_from/date_to were previously not applied to Evidence at all.
            if date_from:
                ev_filters.append("e.email_date >= $date_from")
                params["date_from"] = date_from
            if date_to:
                ev_filters.append("e.email_date <= $date_to")
                params["date_to"] = date_to
            if min_confidence is not None:
                ev_filters.append("e.confidence >= $min_confidence")
                params["min_confidence"] = min_confidence

            where_clause = " AND ".join(ev_filters)
            query = f"""
                MATCH (e:Evidence)
                WHERE {where_clause}
                RETURN e.id AS id, e.quote AS quote,
                       e.confidence AS confidence,
                       e.email_date AS email_date
                ORDER BY e.confidence DESC
                LIMIT $limit
            """
            result = session.run(query, **params)
            items = []
            for r in result:
                quote = r["quote"] or ""
                items.append(SearchResultItem(
                    id=r["id"],
                    name=quote[:120] + ("..." if len(quote) > 120 else ""),
                    type="evidence",
                    snippet=quote[:200] + ("..." if len(quote) > 200 else ""),
                    confidence=r["confidence"],
                    date=r["email_date"],
                ))
            if items:
                groups["evidence"] = SearchResultGroup(
                    type="evidence", label="Evidence",
                    results=items, count=len(items),
                )

        # --- Deal ---
        if type is None or type == "deal":
            result = session.run("""
                MATCH (d:Deal)
                WHERE d.is_deleted = false
                  AND toLower(d.name) CONTAINS toLower($q)
                RETURN d.id AS id, d.name AS name
                LIMIT $limit
            """, q=q_lower, limit=per_type)
            items = []
            for r in result:
                items.append(SearchResultItem(
                    id=r["id"], name=r["name"], type="deal",
                    snippet=r["name"],
                ))
            if items:
                groups["deal"] = SearchResultGroup(
                    type="deal", label="Deals",
                    results=items, count=len(items),
                )

        # --- Decision ---
        if type is None or type == "decision":
            result = session.run("""
                MATCH (dec:Decision)
                WHERE dec.is_deleted = false
                  AND toLower(dec.description) CONTAINS toLower($q)
                RETURN dec.id AS id, dec.description AS description
                LIMIT $limit
            """, q=q_lower, limit=per_type)
            items = []
            for r in result:
                desc = r["description"] or ""
                items.append(SearchResultItem(
                    id=r["id"],
                    name=desc[:120] + ("..." if len(desc) > 120 else ""),
                    type="decision",
                    snippet=desc[:200] + ("..." if len(desc) > 200 else ""),
                ))
            if items:
                groups["decision"] = SearchResultGroup(
                    type="decision", label="Decisions",
                    results=items, count=len(items),
                )

    # Assemble in display order, only non-empty groups
    ordered_groups = []
    for t in TYPE_ORDER:
        if t in groups:
            ordered_groups.append(groups[t])

    total = sum(g.count for g in ordered_groups)

    return GlobalSearchResponse(
        query=q,
        groups=ordered_groups,
        total_results=total,
    )