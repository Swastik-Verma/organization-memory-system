"""
Redaction manager — soft deletes and content redaction.

Core principle: NOTHING is ever hard-deleted. Deleted items are flagged
with is_deleted=True, excluded from retrieval queries, but preserved
for audit trails.

Three operations:
  1. soft_delete_entity   — flag entity + cascade to its claims/evidence
  2. soft_delete_claim    — flag one claim + its evidence
  3. redact_entity        — replace content with [REDACTED] + soft delete

All operations are reversible via restore_entity / restore_claim
(except redaction — content is permanently replaced).

Every operation is recorded in a deletion audit log.

Downstream usage:
  - Neo4j queries: WHERE is_deleted = false (excludes deleted items)
  - Qdrant: deleted evidence removed from vector index (Week 5)
  - Frontend: deleted items hidden from search, graph explorer, chat
  - Audit UI: deleted items visible with deletion metadata
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

REDACTED_PLACEHOLDER = "[REDACTED]"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DeletionRecord:
    """Audit trail for one deletion operation."""
    deletion_id: str
    target_type: str              # "entity" or "claim"
    target_id: str
    target_name: str              # for readability in the audit log
    action: str                   # "soft_delete" or "redact"
    reason: str
    cascaded_claim_ids: list[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = "active"        # "active" or "restored"

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Redaction Manager
# ---------------------------------------------------------------------------

class RedactionManager:
    """Manages soft deletes and content redaction across entities and claims.

    Works on in-memory data structures (entities dict, claims list,
    resolution map). Changes are applied in-place and saved by the
    batch script.

    Usage:
        manager = RedactionManager(entities, claims, resolution_map)

        # Delete an entity and cascade
        record = manager.soft_delete_entity("person:john-arnold", "privacy_request")

        # Delete a specific claim
        record = manager.soft_delete_claim("claim:abc123", "bad_extraction")

        # Redact all content for an entity
        record = manager.redact_entity("person:john-arnold", "legal_compliance")

        # Restore a deletion
        manager.restore_entity("person:john-arnold")
    """

    def __init__(
        self,
        entities: dict[str, dict],
        claims: list[dict],
        resolution_map: dict[str, str],
    ):
        self.entities = entities
        self.claims = claims
        self.resolution_map = resolution_map
        self.deletion_log: list[DeletionRecord] = []
        self._deletion_counter = 0

    def _next_deletion_id(self) -> str:
        self._deletion_counter += 1
        return f"del:{self._deletion_counter:04d}"

    # ------------------------------------------------------------------
    # Soft delete entity
    # ------------------------------------------------------------------

    def soft_delete_entity(self, entity_id: str, reason: str) -> DeletionRecord | None:
        """Soft-delete an entity and cascade to all its claims.

        - Marks the entity as deleted
        - Finds all claims where this entity is subject OR object
        - Marks those claims as deleted
        - Marks evidence within those claims as deleted
        - Records everything in the deletion log

        Does NOT remove the entity from the entities dict or resolution map.
        The flags handle exclusion from queries.
        """
        if entity_id not in self.entities:
            logger.warning("Entity '%s' not found", entity_id)
            return None

        entity = self.entities[entity_id]

        if entity.get("is_deleted"):
            logger.warning("Entity '%s' already deleted", entity_id)
            return None

        timestamp = datetime.now(timezone.utc).isoformat()

        # Mark entity as deleted
        entity["is_deleted"] = True
        entity["deleted_at"] = timestamp
        entity["deletion_reason"] = reason

        # Cascade to claims
        cascaded_ids = []
        for claim in self.claims:
            if claim.get("is_deleted"):
                continue

            subject_match = claim.get("subject_id") == entity_id
            object_match = claim.get("object_id") == entity_id

            if subject_match or object_match:
                claim["is_deleted"] = True
                claim["deleted_at"] = timestamp
                claim["deletion_reason"] = f"cascade:entity:{entity_id}:{reason}"

                # Mark evidence within this claim
                for ev in claim.get("evidence", []):
                    if isinstance(ev, dict):
                        ev["is_deleted"] = True

                cascaded_ids.append(claim["claim_id"])

        # Record
        record = DeletionRecord(
            deletion_id=self._next_deletion_id(),
            target_type="entity",
            target_id=entity_id,
            target_name=entity.get("canonical_name", entity_id),
            action="soft_delete",
            reason=reason,
            cascaded_claim_ids=cascaded_ids,
            timestamp=timestamp,
        )
        self.deletion_log.append(record)

        logger.info(
            "Soft-deleted entity '%s' (%s), cascaded to %d claims",
            entity.get("canonical_name"), entity_id, len(cascaded_ids),
        )
        return record

    # ------------------------------------------------------------------
    # Soft delete claim
    # ------------------------------------------------------------------

    def soft_delete_claim(self, claim_id: str, reason: str) -> DeletionRecord | None:
        """Soft-delete a specific claim and its evidence.

        Does NOT delete the entities connected to this claim.
        An entity may have many claims — deleting one claim doesn't
        mean the entity should disappear.
        """
        claim = self._find_claim(claim_id)
        if claim is None:
            logger.warning("Claim '%s' not found", claim_id)
            return None

        if claim.get("is_deleted"):
            logger.warning("Claim '%s' already deleted", claim_id)
            return None

        timestamp = datetime.now(timezone.utc).isoformat()

        claim["is_deleted"] = True
        claim["deleted_at"] = timestamp
        claim["deletion_reason"] = reason

        # Mark evidence
        for ev in claim.get("evidence", []):
            if isinstance(ev, dict):
                ev["is_deleted"] = True

        record = DeletionRecord(
            deletion_id=self._next_deletion_id(),
            target_type="claim",
            target_id=claim_id,
            target_name=claim.get("description", claim_id),
            action="soft_delete",
            reason=reason,
            timestamp=timestamp,
        )
        self.deletion_log.append(record)

        logger.info("Soft-deleted claim '%s'", claim_id)
        return record

    # ------------------------------------------------------------------
    # Redact entity (content replacement + soft delete)
    # ------------------------------------------------------------------

    def redact_entity(self, entity_id: str, reason: str) -> DeletionRecord | None:
        """Redact all content for an entity.

        More aggressive than soft_delete:
        - Replaces the entity's canonical_name with [REDACTED]
        - Clears aliases and emails
        - Replaces evidence quotes in all connected claims
        - Then soft-deletes everything

        Used for legal/privacy compliance where the actual text
        must be scrubbed, not just hidden.

        WARNING: This is IRREVERSIBLE. The content is permanently
        replaced. restore_entity will refuse to restore a redacted entity.
        """
        if entity_id not in self.entities:
            logger.warning("Entity '%s' not found for redaction", entity_id)
            return None

        entity = self.entities[entity_id]
        original_name = entity.get("canonical_name", entity_id)
        timestamp = datetime.now(timezone.utc).isoformat()

        # Redact entity content
        entity["canonical_name"] = REDACTED_PLACEHOLDER
        entity["aliases"] = [REDACTED_PLACEHOLDER]
        entity["emails"] = []
        entity["is_deleted"] = True
        entity["deleted_at"] = timestamp
        entity["deletion_reason"] = f"redacted:{reason}"

        # Update resolution map: mark entries pointing to this entity
        names_to_redact = [
            name for name, cid in self.resolution_map.items()
            if cid == entity_id
        ]
        for name in names_to_redact:
            self.resolution_map[name] = f"REDACTED:{entity_id}"

        # Redact and delete connected claims
        cascaded_ids = []
        for claim in self.claims:
            subject_match = claim.get("subject_id") == entity_id
            object_match = claim.get("object_id") == entity_id

            if subject_match or object_match:
                if subject_match:
                    claim["subject_name"] = REDACTED_PLACEHOLDER
                if object_match:
                    claim["object_name"] = REDACTED_PLACEHOLDER
                claim["description"] = REDACTED_PLACEHOLDER

                for ev in claim.get("evidence", []):
                    if isinstance(ev, dict):
                        ev["quote"] = REDACTED_PLACEHOLDER
                        ev["is_deleted"] = True

                claim["is_deleted"] = True
                claim["deleted_at"] = timestamp
                claim["deletion_reason"] = f"redacted:cascade:{entity_id}:{reason}"
                cascaded_ids.append(claim["claim_id"])

        record = DeletionRecord(
            deletion_id=self._next_deletion_id(),
            target_type="entity",
            target_id=entity_id,
            target_name=original_name,
            action="redact",
            reason=reason,
            cascaded_claim_ids=cascaded_ids,
            timestamp=timestamp,
        )
        self.deletion_log.append(record)

        logger.info(
            "Redacted entity '%s' (%s), cascaded to %d claims",
            original_name, entity_id, len(cascaded_ids),
        )
        return record

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    def restore_entity(self, entity_id: str) -> bool:
        """Reverse a soft-delete on an entity and its cascaded claims.

        Cannot restore a REDACTED entity — the content has been
        permanently replaced and is unrecoverable.
        """
        if entity_id not in self.entities:
            logger.warning("Entity '%s' not found", entity_id)
            return False

        entity = self.entities[entity_id]
        if not entity.get("is_deleted"):
            logger.warning("Entity '%s' is not deleted", entity_id)
            return False

        if entity.get("deletion_reason", "").startswith("redacted:"):
            logger.warning(
                "Entity '%s' was redacted — content is permanently removed, "
                "cannot restore", entity_id,
            )
            return False

        # Restore entity
        entity["is_deleted"] = False
        entity.pop("deleted_at", None)
        entity.pop("deletion_reason", None)

        # Restore cascaded claims
        cascade_prefix = f"cascade:entity:{entity_id}:"
        restored_claims = 0
        for claim in self.claims:
            reason = claim.get("deletion_reason", "")
            if reason.startswith(cascade_prefix):
                claim["is_deleted"] = False
                claim.pop("deleted_at", None)
                claim.pop("deletion_reason", None)

                for ev in claim.get("evidence", []):
                    if isinstance(ev, dict):
                        ev.pop("is_deleted", None)

                restored_claims += 1

        # Mark deletion record as restored
        for record in reversed(self.deletion_log):
            if (record.target_id == entity_id
                    and record.target_type == "entity"
                    and record.action == "soft_delete"
                    and record.status == "active"):
                record.status = "restored"
                break

        logger.info(
            "Restored entity '%s', restored %d cascaded claims",
            entity_id, restored_claims,
        )
        return True

    def restore_claim(self, claim_id: str) -> bool:
        """Reverse a soft-delete on a specific claim.

        Cannot restore redacted claims.
        """
        claim = self._find_claim(claim_id)
        if claim is None:
            logger.warning("Claim '%s' not found", claim_id)
            return False

        if not claim.get("is_deleted"):
            logger.warning("Claim '%s' is not deleted", claim_id)
            return False

        if "redacted" in claim.get("deletion_reason", ""):
            logger.warning("Claim '%s' was redacted — cannot restore", claim_id)
            return False

        claim["is_deleted"] = False
        claim.pop("deleted_at", None)
        claim.pop("deletion_reason", None)

        for ev in claim.get("evidence", []):
            if isinstance(ev, dict):
                ev.pop("is_deleted", None)

        for record in reversed(self.deletion_log):
            if (record.target_id == claim_id and record.status == "active"):
                record.status = "restored"
                break

        logger.info("Restored claim '%s'", claim_id)
        return True

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_active_entities(self) -> dict[str, dict]:
        """Return only non-deleted entities."""
        return {
            cid: e for cid, e in self.entities.items()
            if not e.get("is_deleted")
        }

    def get_active_claims(self) -> list[dict]:
        """Return only non-deleted claims."""
        return [c for c in self.claims if not c.get("is_deleted")]

    def get_deleted_entities(self) -> dict[str, dict]:
        """Return only deleted entities (for audit view)."""
        return {
            cid: e for cid, e in self.entities.items()
            if e.get("is_deleted")
        }

    def get_deleted_claims(self) -> list[dict]:
        """Return only deleted claims (for audit view)."""
        return [c for c in self.claims if c.get("is_deleted")]

    def get_deletion_log(self) -> list[dict]:
        """Return the full deletion audit log."""
        return [r.to_dict() for r in self.deletion_log]

    def get_stats(self) -> dict:
        """Return deletion statistics."""
        active_deletions = [r for r in self.deletion_log if r.status == "active"]
        restored = [r for r in self.deletion_log if r.status == "restored"]

        return {
            "total_deleted_entities": len(self.get_deleted_entities()),
            "total_deleted_claims": len(self.get_deleted_claims()),
            "total_active_entities": len(self.get_active_entities()),
            "total_active_claims": len(self.get_active_claims()),
            "deletion_operations": len(active_deletions),
            "restore_operations": len(restored),
            "redacted_entities": sum(
                1 for e in self.entities.values()
                if e.get("deletion_reason", "").startswith("redacted:")
            ),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _find_claim(self, claim_id: str) -> dict | None:
        """Find a claim by ID."""
        for claim in self.claims:
            if claim.get("claim_id") == claim_id:
                return claim
        return None