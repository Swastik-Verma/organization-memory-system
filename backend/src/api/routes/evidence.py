"""
Evidence route — drill into a specific evidence excerpt.

GET /api/evidence/{id} — full evidence detail including the
                         source email body for inline highlighting.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import CurrentUser, get_current_user, get_neo4j_driver
from src.api.models import EvidenceDetailResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/evidence/{evidence_id}", response_model=EvidenceDetailResponse)
async def get_evidence(
    evidence_id: str,
    driver=Depends(get_neo4j_driver),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Get full details for a single evidence excerpt.

    Returns the quote, character offsets, parent claim info,
    and the source email body (for inline highlighting in the
    frontend — Day 44).

    The email body allows the frontend to show exactly where
    in the original email the evidence was extracted from,
    using char_start and char_end for highlighting.
    """
    query = """
    MATCH (e:Evidence {evidence_id: $evidence_id})
    WHERE e.is_deleted = false
    OPTIONAL MATCH (c:Claim)-[:SUPPORTED_BY]->(e)
    OPTIONAL MATCH (e)-[:FROM_MESSAGE]->(m:Message)
    RETURN
        e.evidence_id AS evidence_id,
        e.quote AS quote,
        e.char_start AS char_start,
        e.char_end AS char_end,
        e.confidence AS confidence,
        e.evidence_verified AS evidence_verified,
        e.message_id AS message_id,
        c.id AS claim_id,
        c.claim_type AS claim_type,
        c.subject_name AS subject_name,
        c.object_name AS object_name,
        m.subject AS email_subject,
        m.from_addr AS email_from,
        m.date AS email_date,
        m.body AS email_body
    """

    with driver.session() as session:
        record = session.run(query, evidence_id=evidence_id).single()

    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Evidence '{evidence_id}' not found",
        )

    email_date = record["email_date"]

    return EvidenceDetailResponse(
        evidence_id=record["evidence_id"],
        quote=record["quote"] or "",
        message_id=record["message_id"],
        char_start=record["char_start"],
        char_end=record["char_end"],
        confidence=record["confidence"],
        evidence_verified=record["evidence_verified"],
        claim_id=record["claim_id"],
        claim_type=record["claim_type"],
        subject_name=record["subject_name"],
        object_name=record["object_name"],
        email_subject=record["email_subject"],
        email_from=record["email_from"],
        email_date=str(email_date) if email_date else None,
        email_body=record["email_body"],
    )