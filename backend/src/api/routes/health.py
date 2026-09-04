"""
Health route — system status dashboard endpoint.

GET /api/health — checks Neo4j and Qdrant connectivity,
                  returns node/edge/vector counts.

Powers the health dashboard (Day 42) and is useful for
monitoring and debugging.
"""

import logging

from fastapi import APIRouter, Depends
from src.graph.health_monitor import HealthMonitor
from src.api.dependencies import get_neo4j_driver, get_qdrant_index
from src.api.models import HealthResponse, ServiceStatus
from src.retrieval.qdrant_index import QdrantIndex

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    driver=Depends(get_neo4j_driver),
    qdrant: QdrantIndex = Depends(get_qdrant_index),
):
    """
    Check the health of all backend services.

    Returns:
      - Status of Neo4j and Qdrant connections
      - Node counts by label
      - Edge count
      - Vector count in Qdrant
    """
    services = []
    counts = {}
    overall_healthy = True

    # Check Neo4j
    try:
        with driver.session() as session:
            # Connectivity check
            session.run("RETURN 1").single()

            # Node counts by label
            result = session.run("""
                MATCH (n)
                WHERE n.is_deleted = false
                WITH labels(n)[0] AS label, count(n) AS cnt
                RETURN label, cnt
                ORDER BY cnt DESC
            """)
            for r in result:
                counts[r["label"]] = r["cnt"]

            # Edge count
            edge_result = session.run("""
                MATCH ()-[r]->()
                RETURN count(r) AS total_edges
            """)
            counts["total_edges"] = edge_result.single()["total_edges"]

        services.append(ServiceStatus(
            name="neo4j", status="ok",
            detail=f"{sum(v for k, v in counts.items() if k != 'total_edges')} nodes, "
                   f"{counts.get('total_edges', 0)} edges",
        ))

    except Exception as e:
        logger.error("Neo4j health check failed: %s", e)
        services.append(ServiceStatus(
            name="neo4j", status="error", detail=str(e)
        ))
        overall_healthy = False

    # Check Qdrant
    try:
        info = qdrant.get_collection_info()
        counts["vectors"] = info["points_count"]

        services.append(ServiceStatus(
            name="qdrant", status="ok",
            detail=f"{info['points_count']} vectors, status={info['status']}",
        ))

    except Exception as e:
        logger.error("Qdrant health check failed: %s", e)
        services.append(ServiceStatus(
            name="qdrant", status="error", detail=str(e)
        ))
        overall_healthy = False

    # Full metrics report for the dashboard (Day 42)
    report = None
    try:
        monitor = HealthMonitor(driver)
        report = monitor.full_health_report()
    except Exception as e:
        logger.error("Health monitor full report failed: %s", e)
        # Don't flip overall_healthy to False here — connectivity is already
        # verified above; this is richer detail, not a core health check.


    return HealthResponse(
        status="healthy" if overall_healthy else "degraded",
        services=services,
        counts=counts,
        report=report,
    )