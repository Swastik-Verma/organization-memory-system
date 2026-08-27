"""
Entity routes — browse and explore entities in the knowledge graph.

GET /api/entities          — paginated list of all entities
GET /api/entities/{id}     — single entity detail
GET /api/entities/{id}/timeline — chronological claim history
GET /api/entities/{id}/claims   — all claims involving this entity
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import CurrentUser, get_current_user, get_neo4j_driver
from src.api.models import (
    ClaimResult,
    EntityClaimsResponse,
    EntityDetailResponse,
    EntityListItem,
    EntityListResponse,
    EntityTimelineResponse,
    TimelineEvent,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/entities", response_model=EntityListResponse)
async def list_entities(
    entity_type: Optional[str] = Query(
        default=None, description="Filter by type: person, organization"
    ),
    search: Optional[str] = Query(
        default=None, description="Search by name (partial match)"
    ),
    skip: int = Query(default=0, ge=0, description="Offset for pagination"),
    limit: int = Query(default=20, ge=1, le=100, description="Page size"),
    driver=Depends(get_neo4j_driver),
    user: CurrentUser = Depends(get_current_user),
):
    """List all entities with optional filtering and pagination."""

    # Build dynamic WHERE clauses
    conditions = ["n.is_deleted = false"]
    params = {"skip": skip, "limit": limit}

    if search:
        conditions.append("toLower(n.canonical_name) CONTAINS toLower($search)")
        params["search"] = search

    # Build label filter
    if entity_type == "person":
        label = "Person"
    elif entity_type == "organization":
        label = "Organization"
    else:
        label = None

    label_match = f"(n:{label})" if label else "(n:Person) OR (n:Organization)"
    if label:
        match_clause = f"MATCH (n:{label})"
    else:
        match_clause = "MATCH (n) WHERE (n:Person OR n:Organization)"
        # Move the is_deleted condition into an AND
        where_clause = " AND ".join(conditions)
        query = f"""
        {match_clause}
          AND {where_clause}
        RETURN n.id AS id, n.canonical_name AS name,
               labels(n)[0] AS type, n.mention_count AS mention_count
        ORDER BY n.mention_count DESC
        SKIP $skip LIMIT $limit
        """
        count_query = f"""
        {match_clause}
          AND {where_clause}
        RETURN count(n) AS total
        """

        with driver.session() as session:
            total = session.run(count_query, **params).single()["total"]
            result = session.run(query, **params)
            entities = [
                EntityListItem(
                    id=r["id"],
                    name=r["name"],
                    type=r["type"].lower() if r["type"] else "unknown",
                    mention_count=r["mention_count"] or 0,
                )
                for r in result
            ]

        return EntityListResponse(
            entities=entities, total=total, skip=skip, limit=limit
        )

    # With specific label
    where_clause = " AND ".join(conditions)
    query = f"""
    {match_clause}
    WHERE {where_clause}
    RETURN n.id AS id, n.canonical_name AS name,
           labels(n)[0] AS type, n.mention_count AS mention_count
    ORDER BY n.mention_count DESC
    SKIP $skip LIMIT $limit
    """
    count_query = f"""
    {match_clause}
    WHERE {where_clause}
    RETURN count(n) AS total
    """

    with driver.session() as session:
        total = session.run(count_query, **params).single()["total"]
        result = session.run(query, **params)
        entities = [
            EntityListItem(
                id=r["id"],
                name=r["name"],
                type=r["type"].lower() if r["type"] else "unknown",
                mention_count=r["mention_count"] or 0,
            )
            for r in result
        ]

    return EntityListResponse(
        entities=entities, total=total, skip=skip, limit=limit
    )


@router.get("/entities/{entity_id}", response_model=EntityDetailResponse)
async def get_entity(
    entity_id: str,
    driver=Depends(get_neo4j_driver),
    user: CurrentUser = Depends(get_current_user),
):
    """Get detailed information about a single entity."""
    query = """
    MATCH (n)
    WHERE n.id = $entity_id AND n.is_deleted = false
      AND (n:Person OR n:Organization)
    RETURN n.id AS id, n.canonical_name AS name,
           labels(n)[0] AS type,
           n.mention_count AS mention_count,
           n.aliases AS aliases,
           n.emails AS emails,
           n.org_type AS org_type
    """
    with driver.session() as session:
        record = session.run(query, entity_id=entity_id).single()

    if not record:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    return EntityDetailResponse(
        id=record["id"],
        name=record["name"],
        type=record["type"].lower() if record["type"] else "unknown",
        mention_count=record["mention_count"] or 0,
        aliases=record["aliases"] or [],
        emails=record["emails"] or [],
        org_type=record["org_type"],
    )


@router.get(
    "/entities/{entity_id}/timeline",
    response_model=EntityTimelineResponse,
)
async def get_entity_timeline(
    entity_id: str,
    driver=Depends(get_neo4j_driver),
    user: CurrentUser = Depends(get_current_user),
):
    """Get the chronological timeline of claims for an entity."""
    # First get entity name
    name_query = """
    MATCH (n) WHERE n.id = $entity_id AND n.is_deleted = false
    RETURN n.canonical_name AS name
    """

    # Then get all claims ordered by time
    claims_query = """
    MATCH (c:Claim)
    WHERE (c.subject_id = $entity_id OR c.object_id = $entity_id)
      AND c.is_deleted = false
      AND c.access_level <= $clearance
    RETURN
        c.id AS claim_id,
        c.claim_type AS claim_type,
        c.subject_name AS subject_name,
        c.object_name AS object_name,
        c.description AS description,
        c.valid_from AS valid_from,
        c.valid_to AS valid_to,
        c.status AS status,
        c.confidence AS confidence
    ORDER BY c.valid_from ASC
    """

    with driver.session() as session:
        name_record = session.run(name_query, entity_id=entity_id).single()
        if not name_record:
            raise HTTPException(
                status_code=404, detail=f"Entity '{entity_id}' not found"
            )

        result = session.run(
            claims_query,
            entity_id=entity_id,
            clearance=user.clearance,
        )

        events = []
        for r in result:
            valid_from = r["valid_from"]
            valid_to = r["valid_to"]

            events.append(TimelineEvent(
                claim_id=r["claim_id"],
                claim_type=r["claim_type"] or "",
                subject_name=r["subject_name"] or "",
                object_name=r["object_name"] or "",
                description=r["description"] or "",
                valid_from=str(valid_from) if valid_from else None,
                valid_to=str(valid_to) if valid_to else None,
                status=r["status"] or "",
                confidence=r["confidence"] or 0.0,
            ))

    return EntityTimelineResponse(
        entity_id=entity_id,
        entity_name=name_record["name"] or "",
        events=events,
    )


@router.get(
    "/entities/{entity_id}/claims",
    response_model=EntityClaimsResponse,
)
async def get_entity_claims(
    entity_id: str,
    claim_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    driver=Depends(get_neo4j_driver),
    user: CurrentUser = Depends(get_current_user),
):
    """Get all claims involving this entity with optional filters."""
    conditions = [
        "(c.subject_id = $entity_id OR c.object_id = $entity_id)",
        "c.is_deleted = false",
        "c.access_level <= $clearance",
    ]
    params = {"entity_id": entity_id, "clearance": user.clearance}

    if claim_type:
        conditions.append("c.claim_type = $claim_type")
        params["claim_type"] = claim_type

    if status:
        conditions.append("c.status = $status")
        params["status"] = status

    where_clause = " AND ".join(conditions)

    query = f"""
    MATCH (c:Claim)
    WHERE {where_clause}
    RETURN
        c.id AS claim_id,
        c.claim_type AS claim_type,
        c.subject_id AS subject_id,
        c.subject_name AS subject_name,
        c.object_id AS object_id,
        c.object_name AS object_name,
        c.confidence AS confidence,
        c.valid_from AS valid_from,
        c.valid_to AS valid_to,
        c.status AS status,
        c.mention_count AS mention_count
    ORDER BY c.confidence DESC
    """

    with driver.session() as session:
        result = session.run(query, **params)
        claims = []
        for r in result:
            claims.append(ClaimResult(
                claim_id=r["claim_id"],
                claim_type=r["claim_type"] or "",
                subject_id=r["subject_id"] or "",
                subject_name=r["subject_name"] or "",
                object_id=r["object_id"] or "",
                object_name=r["object_name"] or "",
                confidence=r["confidence"] or 0.0,
                valid_from=str(r["valid_from"]) if r["valid_from"] else None,
                valid_to=str(r["valid_to"]) if r["valid_to"] else None,
                status=r["status"] or "",
                mention_count=r["mention_count"] or 0,
                source="graph",
            ))

    return EntityClaimsResponse(
        entity_id=entity_id,
        claims=claims,
        total=len(claims),
    )