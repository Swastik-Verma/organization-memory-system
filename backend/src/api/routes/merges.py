"""
Merge audit log routes — list all entity merges and undo fuzzy merges.

GET  /api/merges              — combined list of Day 16 + Day 17 merges
POST /api/merges/{merge_id}/undo — undo a Day 17 fuzzy merge
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_neo4j_driver
from src.api.models import MergeItem, MergeListResponse, MergeUndoResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Path to the merge data files — same convention as batch scripts
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"


def _load_exact_merges() -> list[MergeItem]:
    """Load Day 16 exact merges from entity_resolution_exact.json."""
    path = DATA_DIR / "entity_resolution_exact.json"
    if not path.exists():
        logger.warning("Exact resolution file not found: %s", path)
        return []

    data = json.loads(path.read_text())
    merge_log = data.get("merge_log", [])

    items = []
    for entry in merge_log:
        items.append(MergeItem(
            merge_id=None,
            source_name=entry["merged_name"],
            target_name=entry["into_canonical_name"],
            source_id=None,
            target_id=entry["into_canonical_id"],
            strategy=entry["reason"],
            confidence=entry["confidence"],
            timestamp=entry["timestamp"],
            status="active",
            phase="exact",
            undoable=False,
        ))
    return items


def _load_fuzzy_merges() -> list[MergeItem]:
    """Load Day 17 fuzzy merges from entity_resolution_fuzzy.json."""
    path = DATA_DIR / "entity_resolution_fuzzy.json"
    if not path.exists():
        logger.warning("Fuzzy resolution file not found: %s", path)
        return []

    data = json.loads(path.read_text())
    operations = data.get("merge_operations", [])

    items = []
    for op in operations:
        items.append(MergeItem(
            merge_id=op["merge_id"],
            source_name=op["source_snapshot"]["canonical_name"],
            target_name=op["target_snapshot"]["canonical_name"],
            source_id=op["source_id"],
            target_id=op["target_id"],
            strategy=op["strategy"],
            confidence=op["confidence"],
            timestamp=op["timestamp"],
            status=op.get("status", "active"),
            phase="fuzzy",
            undoable=op.get("status", "active") == "active",
        ))
    return items


@router.get("/merges", response_model=MergeListResponse)
async def list_merges(
    phase: str | None = None,
    status: str | None = None,
    strategy: str | None = None,
):
    """
    List all entity merges from both resolution phases.

    Optional filters:
      - phase: "exact" or "fuzzy"
      - status: "active" or "undone"
      - strategy: "email_match", "fuzzy", "nickname", etc.
    """
    exact = _load_exact_merges()
    fuzzy = _load_fuzzy_merges()
    all_merges = exact + fuzzy

    # Apply filters
    if phase:
        all_merges = [m for m in all_merges if m.phase == phase]
    if status:
        all_merges = [m for m in all_merges if m.status == status]
    if strategy:
        all_merges = [m for m in all_merges if m.strategy == strategy]

    # Sort by timestamp descending (most recent first)
    all_merges.sort(key=lambda m: m.timestamp, reverse=True)

    return MergeListResponse(
        merges=all_merges,
        total=len(all_merges),
        exact_count=len([m for m in all_merges if m.phase == "exact"]),
        fuzzy_count=len([m for m in all_merges if m.phase == "fuzzy"]),
    )


@router.post("/merges/{merge_id}/undo", response_model=MergeUndoResponse)
async def undo_merge(
    merge_id: str,
    driver=Depends(get_neo4j_driver),
):
    """
    Undo a Day 17 fuzzy merge.

    Restores entity identity (names, aliases, emails, mention_count) in Neo4j.
    Does NOT reassign claims — claims keep their current subject_id/object_id.
    This is a documented limitation: claim-to-entity assignment happened during
    Week 3 claim dedup and there is no stored mapping of which claims belonged
    to which pre-merge identity.
    """
    # Load the fuzzy file to find the operation
    fuzzy_path = DATA_DIR / "entity_resolution_fuzzy.json"
    if not fuzzy_path.exists():
        raise HTTPException(status_code=404, detail="Fuzzy resolution file not found")

    data = json.loads(fuzzy_path.read_text())
    operations = data.get("merge_operations", [])

    # Find the specific operation
    op_index = None
    op = None
    for i, candidate in enumerate(operations):
        if candidate["merge_id"] == merge_id:
            op_index = i
            op = candidate
            break

    if op is None:
        raise HTTPException(status_code=404, detail=f"Merge operation {merge_id} not found")

    if op["status"] == "undone":
        raise HTTPException(status_code=400, detail=f"Merge {merge_id} is already undone")

    source_snapshot = op["source_snapshot"]
    target_snapshot = op["target_snapshot"]
    entity_type = source_snapshot["entity_type"]
    label = "Person" if entity_type == "person" else "Organization"

    try:
        with driver.session() as session:
            # 1. Recreate the source entity node from its snapshot
            session.run(f"""
                MERGE (n:{label} {{id: $id}})
                SET n.canonical_name = $name,
                    n.entity_type = $entity_type,
                    n.aliases = $aliases,
                    n.emails = $emails,
                    n.mention_count = $mentions,
                    n.is_deleted = false
            """, {
                "id": source_snapshot["canonical_id"],
                "name": source_snapshot["canonical_name"],
                "entity_type": entity_type,
                "aliases": source_snapshot.get("aliases", []),
                "emails": source_snapshot.get("emails", []),
                "mentions": source_snapshot.get("mention_count", 0),
            })

            # 2. Restore the target entity to its pre-merge state
            session.run(f"""
                MATCH (n:{label} {{id: $id}})
                SET n.canonical_name = $name,
                    n.aliases = $aliases,
                    n.emails = $emails,
                    n.mention_count = $mentions
            """, {
                "id": target_snapshot["canonical_id"],
                "name": target_snapshot["canonical_name"],
                "aliases": target_snapshot.get("aliases", []),
                "emails": target_snapshot.get("emails", []),
                "mentions": target_snapshot.get("mention_count", 0),
            })

        # 3. Update the file to mark this operation as undone
        data["merge_operations"][op_index]["status"] = "undone"
        fuzzy_path.write_text(json.dumps(data, indent=2))

        return MergeUndoResponse(
            success=True,
            message=f"Merge undone: '{source_snapshot['canonical_name']}' restored as separate entity. "
                    f"Note: existing claims are not reassigned.",
            merge_id=merge_id,
        )

    except Exception as e:
        logger.error("Failed to undo merge %s: %s", merge_id, e)
        raise HTTPException(status_code=500, detail=f"Undo failed: {str(e)}")