"""
Graph routes — explore the knowledge graph structure.

GET /api/graph/{id}/subgraph — get nearby nodes and edges for visualization
GET /api/graph/search         — search entities by name
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import CurrentUser, get_current_user, get_neo4j_driver
from src.api.models import (
    GraphEdge,
    GraphNode,
    GraphSearchResponse,
    GraphSearchResult,
    SubgraphResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/graph/{node_id}/subgraph", response_model=SubgraphResponse)
async def get_subgraph(
    node_id: str,
    depth: int = Query(default=1, ge=1, le=2, description="Traversal depth (1-2)"),
    limit: int = Query(default=50, ge=1, le=200, description="Max neighbor nodes"),
    driver=Depends(get_neo4j_driver),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Get the subgraph around a node for the graph explorer.

    Returns the center node, its immediate neighbors (depth 1),
    and the edges connecting them. Supports depth=2 to include
    neighbors of neighbors.

    This endpoint powers the visual graph explorer (Day 38-39).
    It returns Decision→AFFECTS edges, Deal→PARTY edges,
    Claim→SUBJECT/OBJECT edges — everything Day 31 retrieval
    doesn't cover.
    """
    # First verify the center node exists
    check_query = """
    MATCH (n)
    WHERE n.id = $node_id AND n.is_deleted = false
    RETURN n.id AS id, 
           coalesce(n.canonical_name, n.name, n.description, n.id) AS label,
           labels(n)[0] AS type,
           n.mention_count AS mention_count
    """

    with driver.session() as session:
        center = session.run(check_query, node_id=node_id).single()

    if not center:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

    # Fetch neighbors and edges
    if depth == 1:
        neighbor_query = """
        MATCH (n {id: $node_id})-[r]-(neighbor)
        WHERE NOT neighbor.is_deleted
        RETURN DISTINCT
            neighbor.id AS neighbor_id,
            coalesce(neighbor.canonical_name, neighbor.name, 
                     neighbor.description, neighbor.id) AS neighbor_label,
            labels(neighbor)[0] AS neighbor_type,
            neighbor.mention_count AS mention_count,
            type(r) AS rel_type,
            startNode(r).id AS source_id,
            endNode(r).id AS target_id
        LIMIT $limit
        """
    else:
        neighbor_query = """
        MATCH path = (n {id: $node_id})-[*1..2]-(neighbor)
        WHERE NOT neighbor.is_deleted AND neighbor.id <> $node_id
        WITH DISTINCT neighbor,
             relationships(path) AS rels
        UNWIND rels AS r
        WITH DISTINCT neighbor, r
        RETURN DISTINCT
            neighbor.id AS neighbor_id,
            coalesce(neighbor.canonical_name, neighbor.name,
                     neighbor.description, neighbor.id) AS neighbor_label,
            labels(neighbor)[0] AS neighbor_type,
            neighbor.mention_count AS mention_count,
            type(r) AS rel_type,
            startNode(r).id AS source_id,
            endNode(r).id AS target_id
        LIMIT $limit
        """

    with driver.session() as session:
        result = session.run(
            neighbor_query, node_id=node_id, limit=limit
        )
        rows = [dict(r) for r in result]

    # Build node set (center + neighbors)
    nodes = {
        center["id"]: GraphNode(
            id=center["id"],
            label=center["label"],
            type=center["type"].lower() if center["type"] else "unknown",
            mention_count=center["mention_count"] or 0,
        )
    }

    edges = []
    seen_edges = set()

    for row in rows:
        # Add neighbor node
        nid = row["neighbor_id"]
        if nid and nid not in nodes:
            nodes[nid] = GraphNode(
                id=nid,
                label=row["neighbor_label"] or nid,
                type=(row["neighbor_type"].lower()
                      if row["neighbor_type"] else "unknown"),
                mention_count=row["mention_count"] or 0,
            )

        # Add edge (deduplicated)
        source = row["source_id"]
        target = row["target_id"]
        rel_type = row["rel_type"]

        if source and target:
            edge_key = f"{source}-{rel_type}-{target}"
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges.append(GraphEdge(
                    source=source,
                    target=target,
                    type=rel_type,
                ))

    return SubgraphResponse(
        center_id=node_id,
        nodes=list(nodes.values()),
        edges=edges,
    )


@router.get("/graph/search", response_model=GraphSearchResponse)
async def search_graph(
    q: str = Query(..., min_length=1, description="Search query"),
    entity_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    driver=Depends(get_neo4j_driver),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Search for entities by name across all node types.

    Searches Person, Organization, Deal, and Decision nodes.
    Returns matches sorted by mention_count.
    """
    query = """
    MATCH (p:Person)
    WHERE p.is_deleted = false
      AND (toLower(p.canonical_name) CONTAINS toLower($q)
           OR any(alias IN p.aliases 
                  WHERE toLower(alias) CONTAINS toLower($q)
                        AND NOT alias CONTAINS '@'))
    RETURN p.id AS id, p.canonical_name AS name,
           'person' AS type, p.mention_count AS mention_count

    UNION

    MATCH (o:Organization)
    WHERE o.is_deleted = false
      AND (toLower(o.canonical_name) CONTAINS toLower($q)
           OR any(alias IN o.aliases
                  WHERE toLower(alias) CONTAINS toLower($q)))
    RETURN o.id AS id, o.canonical_name AS name,
           'organization' AS type, o.mention_count AS mention_count

    UNION

    MATCH (d:Deal)
    WHERE d.is_deleted = false
      AND toLower(d.name) CONTAINS toLower($q)
    RETURN d.id AS id, d.name AS name,
           'deal' AS type, 1 AS mention_count

    UNION

    MATCH (dec:Decision)
    WHERE dec.is_deleted = false
      AND toLower(dec.description) CONTAINS toLower($q)
    RETURN dec.id AS id, dec.description AS name,
           'decision' AS type, 1 AS mention_count
    """

    with driver.session() as session:
        result = session.run(query, q=q)
        all_results = [dict(r) for r in result]

    # Filter by type if specified
    if entity_type:
        all_results = [
            r for r in all_results
            if r["type"] == entity_type
        ]

    # Sort by mention count and limit
    all_results.sort(
        key=lambda r: r.get("mention_count", 0), reverse=True
    )
    all_results = all_results[:limit]

    results = [
        GraphSearchResult(
            id=r["id"],
            name=r["name"],
            type=r["type"],
            mention_count=r["mention_count"] or 0,
        )
        for r in all_results
    ]

    return GraphSearchResponse(query=q, results=results)