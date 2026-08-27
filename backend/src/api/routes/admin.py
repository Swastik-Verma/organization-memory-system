"""
Admin routes — conflict resolution and review queue.

GET /api/conflicts     — list unresolved claim conflicts
GET /api/review-queue  — claims needing human review
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import CurrentUser, get_current_user, get_neo4j_driver
from src.api.models import (
    ConflictItem,
    ConflictListResponse,
    ReviewItem,
    ReviewQueueResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/conflicts", response_model=ConflictListResponse)
async def list_conflicts(
    limit: int = Query(default=50, ge=1, le=200),
    driver=Depends(get_neo4j_driver),
    user: CurrentUser = Depends(get_current_user),
):
    """
    List claims that have unresolved conflicts.

    A conflict exists when two claims contradict each other —
    e.g. "X reports to Y" and "X reports to Z" for the same
    time period. These were detected during deduplication
    (Day 19) and stored in the conflicts_with property.

    The conflict review queue (Day 44 frontend) lets a human
    resolve these by choosing which claim is correct.
    """
    query = """
    MATCH (c:Claim)
    WHERE c.is_deleted = false
      AND c.conflicts_with IS NOT NULL
      AND size(c.conflicts_with) > 0
      AND c.access_level <= $clearance
    RETURN
        c.id AS claim_id,
        c.claim_type AS claim_type,
        c.subject_name AS subject_name,
        c.object_name AS object_name,
        c.conflicts_with AS conflicts_with,
        c.confidence AS confidence
    ORDER BY c.confidence DESC
    LIMIT $limit
    """

    with driver.session() as session:
        result = session.run(
            query, clearance=user.clearance, limit=limit
        )
        conflicts = []
        for r in result:
            conflicts.append(ConflictItem(
                claim_id=r["claim_id"],
                claim_type=r["claim_type"] or "",
                subject_name=r["subject_name"] or "",
                object_name=r["object_name"] or "",
                conflicts_with=r["conflicts_with"] or [],
                confidence=r["confidence"] or 0.0,
            ))

    return ConflictListResponse(
        conflicts=conflicts,
        total=len(conflicts),
    )


@router.get("/review-queue", response_model=ReviewQueueResponse)
async def get_review_queue(
    limit: int = Query(default=50, ge=1, le=200),
    driver=Depends(get_neo4j_driver),
    user: CurrentUser = Depends(get_current_user),
):
    """
    List claims that need human review.

    A claim needs review when:
      - status is "review" (flagged during deduplication)
      - confidence is below 0.5 (low-quality extraction)
      - It has conflicts with other claims

    This powers the conflict review queue (Day 44 frontend)
    where a human can approve, reject, or modify claims.
    """
    query = """
    MATCH (c:Claim)
    WHERE c.is_deleted = false
      AND c.access_level <= $clearance
      AND (
          c.status = 'review'
          OR c.confidence < 0.5
          OR (c.conflicts_with IS NOT NULL AND size(c.conflicts_with) > 0)
      )
    RETURN
        c.id AS claim_id,
        c.claim_type AS claim_type,
        c.subject_name AS subject_name,
        c.object_name AS object_name,
        c.status AS status,
        c.confidence AS confidence,
        CASE
            WHEN c.status = 'review' THEN 'Flagged for review during deduplication'
            WHEN c.confidence < 0.5 THEN 'Low confidence extraction'
            WHEN c.conflicts_with IS NOT NULL 
                 AND size(c.conflicts_with) > 0 THEN 'Has conflicting claims'
            ELSE 'Unknown'
        END AS reason
    ORDER BY c.confidence ASC
    LIMIT $limit
    """

    with driver.session() as session:
        result = session.run(
            query, clearance=user.clearance, limit=limit
        )
        items = []
        for r in result:
            items.append(ReviewItem(
                claim_id=r["claim_id"],
                claim_type=r["claim_type"] or "",
                subject_name=r["subject_name"] or "",
                object_name=r["object_name"] or "",
                status=r["status"] or "",
                confidence=r["confidence"] or 0.0,
                reason=r["reason"] or "",
            ))

    return ReviewQueueResponse(
        items=items,
        total=len(items),
    )