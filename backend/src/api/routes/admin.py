"""
Admin routes — conflict resolution and review queue.

GET /api/conflicts     — list unresolved claim conflicts
GET /api/review-queue  — claims needing human review
"""

import logging
from typing import Optional
import json
from pathlib import Path 

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import CurrentUser, get_current_user, get_neo4j_driver
from src.api.models import (
    ConflictItem,
    ConflictListResponse,
    ConflictGroup,
    ConflictGroupListResponse,
    ConflictClaimDetail,
    ConflictResolveRequest,
    ConflictResolveResponse,
    ReviewItem,
    ReviewQueueResponse,
    AutoResolvedConflict,
    AutoResolvedListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"

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


@router.get("/conflict-groups", response_model=ConflictGroupListResponse)
async def list_conflict_groups(
    driver=Depends(get_neo4j_driver),
):
    """
    List all conflict groups from the Day 19 conflict review queue.
    Enriches each claim with its evidence and each subject with aliases,
    by querying Neo4j alongside the JSON file.
    """
    path = DATA_DIR / "conflict_review_queue.json"
    if not path.exists():
        return ConflictGroupListResponse(conflicts=[], total=0)

    data = json.loads(path.read_text())
    raw_conflicts = data.get("conflicts", [])

    # Collect all claim_ids and subject_ids up front for batched queries
    all_claim_ids = []
    all_subject_ids = []
    for entry in raw_conflicts:
        all_subject_ids.append(entry["subject_id"])
        for c in entry.get("claims", []):
            all_claim_ids.append(c["claim_id"])

    evidence_map = {}   # claim_id -> {evidence_id, evidence_count}
    aliases_map = {}    # subject_id -> [aliases]

    with driver.session() as session:
        # Batched: evidence for every claim in one query
        result = session.run("""
            UNWIND $claim_ids AS cid
            MATCH (c:Claim {id: cid})-[:SUPPORTED_BY]->(e:Evidence)
            WITH cid, e ORDER BY e.confidence DESC
            WITH cid, collect(e.id) AS evidence_ids
            RETURN cid, evidence_ids[0] AS evidence_id, size(evidence_ids) AS evidence_count
        """, claim_ids=all_claim_ids)
        for r in result:
            evidence_map[r["cid"]] = {
                "evidence_id": r["evidence_id"],
                "evidence_count": r["evidence_count"],
            }

        # Batched: aliases for every subject (always Person for reports_to)
        result = session.run("""
            UNWIND $subject_ids AS sid
            MATCH (p:Person {id: sid})
            RETURN sid, p.aliases AS aliases
        """, subject_ids=all_subject_ids)
        for r in result:
            aliases_map[r["sid"]] = r["aliases"] or []

    groups = []
    for entry in raw_conflicts:
        claims = []
        for c in entry.get("claims", []):
            ev = evidence_map.get(c["claim_id"], {})
            claims.append(ConflictClaimDetail(
                claim_id=c["claim_id"],
                object_id=c.get("object_id", ""),
                object_name=c.get("object_name", ""),
                mention_count=c.get("mention_count", 0),
                valid_from=c.get("valid_from"),
                confidence=c.get("confidence", 0.0),
                evidence_id=ev.get("evidence_id"),
                evidence_count=ev.get("evidence_count", 0),
            ))

        groups.append(ConflictGroup(
            conflict_id=entry["conflict_id"],
            claim_type=entry.get("claim_type", ""),
            subject_id=entry.get("subject_id", ""),
            subject_name=entry.get("subject_name", ""),
            subject_aliases=aliases_map.get(entry.get("subject_id", ""), []),
            classification=entry.get("classification", ""),
            resolution=entry.get("resolution", ""),
            reason=entry.get("reason", ""),
            claims=claims,
            current_claim_id=entry.get("current_claim_id"),
            timestamp=entry.get("timestamp", ""),
        ))

    needs_review = len([g for g in groups if g.resolution == "needs_review"])
    resolved = len([g for g in groups if g.resolution != "needs_review"])

    return ConflictGroupListResponse(
        conflicts=groups,
        total=len(groups),
        needs_review=needs_review,
        resolved=resolved,
    )

@router.get("/conflict-resolutions", response_model=AutoResolvedListResponse)
async def list_auto_resolved_conflicts(
    driver=Depends(get_neo4j_driver),
):
    """
    List all auto-resolved temporal succession conflicts (read-only).
    """
    path = DATA_DIR / "conflict_resolutions.json"
    if not path.exists():
        return AutoResolvedListResponse(conflicts=[], total=0)

    data = json.loads(path.read_text())
    raw = data.get("resolutions", [])
    auto_resolved = [r for r in raw if r.get("resolution") == "auto_resolved"]

    # Batched alias lookup for all subjects
    subject_ids = [entry["subject_id"] for entry in auto_resolved]
    aliases_map = {}
    with driver.session() as session:
        result = session.run("""
            UNWIND $subject_ids AS sid
            MATCH (p:Person {id: sid})
            RETURN sid, p.aliases AS aliases
        """, subject_ids=subject_ids)
        for r in result:
            aliases_map[r["sid"]] = r["aliases"] or []

    conflicts = []
    for entry in auto_resolved:
        claims = []
        for c in entry.get("claims", []):
            claims.append(ConflictClaimDetail(
                claim_id=c["claim_id"],
                object_id=c.get("object_id", ""),
                object_name=c.get("object_name", ""),
                mention_count=c.get("mention_count", 0),
                valid_from=c.get("valid_from"),
                confidence=c.get("confidence", 0.0),
            ))
        claims.sort(key=lambda c: c.valid_from or "9999-12-31")

        conflicts.append(AutoResolvedConflict(
            conflict_id=entry["conflict_id"],
            claim_type=entry.get("claim_type", ""),
            subject_id=entry.get("subject_id", ""),
            subject_name=entry.get("subject_name", ""),
            subject_aliases=aliases_map.get(entry.get("subject_id", ""), []),
            classification=entry.get("classification", ""),
            resolution=entry.get("resolution", ""),
            reason=entry.get("reason", ""),
            claims=claims,
            superseded_claim_ids=entry.get("superseded_claim_ids", []),
            current_claim_id=entry.get("current_claim_id"),
            timestamp=entry.get("timestamp", ""),
        ))

    return AutoResolvedListResponse(conflicts=conflicts, total=len(conflicts))

    
@router.post("/conflict-groups/{conflict_id}/resolve", response_model=ConflictResolveResponse)
async def resolve_conflict(
    conflict_id: str,
    body: ConflictResolveRequest,
    driver=Depends(get_neo4j_driver),
):
    """
    Resolve a conflict group.

    Actions:
      - "keep_one": mark winning_claim_id as current, supersede the rest.
        Creates SUPERSEDES edges, sets losers' status to "superseded",
        removes CONFLICTS_WITH edges.
      - "all_historical": mark all claims in the group as superseded.
        Removes CONFLICTS_WITH edges.
      - "dismiss": the conflict is not real (e.g. person legitimately
        reported to multiple people at the same time). Removes
        CONFLICTS_WITH edges, keeps all claims as "current".
    """
    # Load the file to find the conflict
    path = DATA_DIR / "conflict_review_queue.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Conflict review queue file not found")

    data = json.loads(path.read_text())
    raw_conflicts = data.get("conflicts", [])

    # Find the conflict group
    group_index = None
    group = None
    for i, entry in enumerate(raw_conflicts):
        if entry["conflict_id"] == conflict_id:
            group_index = i
            group = entry
            break

    if group is None:
        raise HTTPException(status_code=404, detail=f"Conflict {conflict_id} not found")

    if group["resolution"] != "needs_review":
        raise HTTPException(status_code=400, detail=f"Conflict {conflict_id} is already resolved")

    claim_ids = [c["claim_id"] for c in group["claims"]]

    if body.action == "keep_one":
        if not body.winning_claim_id:
            raise HTTPException(status_code=400, detail="winning_claim_id required for keep_one")
        if body.winning_claim_id not in claim_ids:
            raise HTTPException(status_code=400, detail="winning_claim_id not in this conflict group")

        loser_ids = [cid for cid in claim_ids if cid != body.winning_claim_id]

        try:
            with driver.session() as session:
                # Mark winner as current
                session.run("""
                    MATCH (c:Claim {id: $claim_id})
                    SET c.status = 'current', c.conflicts_with = []
                """, claim_id=body.winning_claim_id)

                # Mark losers as superseded
                for loser_id in loser_ids:
                    session.run("""
                        MATCH (c:Claim {id: $claim_id})
                        SET c.status = 'superseded',
                            c.superseded_by = $winner_id,
                            c.conflicts_with = []
                    """, claim_id=loser_id, winner_id=body.winning_claim_id)

                    # Create SUPERSEDES edge
                    session.run("""
                        MATCH (winner:Claim {id: $winner_id})
                        MATCH (loser:Claim {id: $loser_id})
                        MERGE (winner)-[:SUPERSEDES]->(loser)
                    """, winner_id=body.winning_claim_id, loser_id=loser_id)

                # Remove CONFLICTS_WITH edges between all claims in this group
                session.run("""
                    UNWIND $ids AS id1
                    UNWIND $ids AS id2
                    WITH id1, id2 WHERE id1 <> id2
                    MATCH (c1:Claim {id: id1})-[r:CONFLICTS_WITH]-(c2:Claim {id: id2})
                    DELETE r
                """, ids=claim_ids)

        except Exception as e:
            logger.error("Failed to resolve conflict %s: %s", conflict_id, e)
            raise HTTPException(status_code=500, detail=f"Resolution failed: {str(e)}")

        # Update file
        data["conflicts"][group_index]["resolution"] = "resolved"
        data["conflicts"][group_index]["current_claim_id"] = body.winning_claim_id
        data["conflicts"][group_index]["superseded_claim_ids"] = loser_ids
        path.write_text(json.dumps(data, indent=2))

        winner_name = next(
            (c["object_name"] for c in group["claims"] if c["claim_id"] == body.winning_claim_id),
            "unknown"
        )
        return ConflictResolveResponse(
            success=True,
            message=f"Resolved: {group['subject_name']} reports_to {winner_name}. "
                    f"{len(loser_ids)} claim(s) superseded.",
            conflict_id=conflict_id,
        )

    elif body.action == "all_historical":
        try:
            with driver.session() as session:
                for cid in claim_ids:
                    session.run("""
                        MATCH (c:Claim {id: $claim_id})
                        SET c.status = 'superseded', c.conflicts_with = []
                    """, claim_id=cid)

                session.run("""
                    UNWIND $ids AS id1
                    UNWIND $ids AS id2
                    WITH id1, id2 WHERE id1 <> id2
                    MATCH (c1:Claim {id: id1})-[r:CONFLICTS_WITH]-(c2:Claim {id: id2})
                    DELETE r
                """, ids=claim_ids)

        except Exception as e:
            logger.error("Failed to resolve conflict %s: %s", conflict_id, e)
            raise HTTPException(status_code=500, detail=f"Resolution failed: {str(e)}")

        data["conflicts"][group_index]["resolution"] = "resolved"
        data["conflicts"][group_index]["superseded_claim_ids"] = claim_ids
        path.write_text(json.dumps(data, indent=2))

        return ConflictResolveResponse(
            success=True,
            message=f"All {len(claim_ids)} claims marked as historical.",
            conflict_id=conflict_id,
        )

    elif body.action == "dismiss":
        try:
            with driver.session() as session:
                for cid in claim_ids:
                    session.run("""
                        MATCH (c:Claim {id: $claim_id})
                        SET c.status = 'current', c.conflicts_with = []
                    """, claim_id=cid)

                session.run("""
                    UNWIND $ids AS id1
                    UNWIND $ids AS id2
                    WITH id1, id2 WHERE id1 <> id2
                    MATCH (c1:Claim {id: id1})-[r:CONFLICTS_WITH]-(c2:Claim {id: id2})
                    DELETE r
                """, ids=claim_ids)

        except Exception as e:
            logger.error("Failed to resolve conflict %s: %s", conflict_id, e)
            raise HTTPException(status_code=500, detail=f"Resolution failed: {str(e)}")

        data["conflicts"][group_index]["resolution"] = "dismissed"
        path.write_text(json.dumps(data, indent=2))

        return ConflictResolveResponse(
            success=True,
            message=f"Conflict dismissed — all {len(claim_ids)} claims kept as current.",
            conflict_id=conflict_id,
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")