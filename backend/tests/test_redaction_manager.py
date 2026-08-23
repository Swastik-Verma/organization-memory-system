"""
Unit tests for redaction manager (Day 20).

Tests soft delete, cascading, content redaction, restore, and edge cases.
"""

import pytest
from src.deduplication.redaction_manager import (
    RedactionManager,
    DeletionRecord,
    REDACTED_PLACEHOLDER,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_test_entities():
    return {
        "person:alice": {
            "canonical_id": "person:alice",
            "canonical_name": "Alice Smith",
            "entity_type": "person",
            "aliases": ["Alice Smith", "A. Smith"],
            "emails": ["alice@enron.com"],
            "mention_count": 500,
        },
        "person:bob": {
            "canonical_id": "person:bob",
            "canonical_name": "Bob Jones",
            "entity_type": "person",
            "aliases": ["Bob Jones"],
            "emails": ["bob@enron.com"],
            "mention_count": 300,
        },
    }


def make_test_claims():
    return [
        {
            "claim_id": "claim:001",
            "claim_type": "reports_to",
            "subject_id": "person:alice",
            "object_id": "person:bob",
            "subject_name": "Alice Smith",
            "object_name": "Bob Jones",
            "description": "Alice Smith reports_to Bob Jones",
            "evidence": [
                {"message_id": "msg1", "quote": "Alice reports to Bob"},
                {"message_id": "msg2", "quote": "Smith under Jones"},
            ],
            "confidence": 0.95,
        },
        {
            "claim_id": "claim:002",
            "claim_type": "works_with",
            "subject_id": "person:alice",
            "object_id": "person:charlie",
            "subject_name": "Alice Smith",
            "object_name": "Charlie Brown",
            "description": "Alice Smith works_with Charlie Brown",
            "evidence": [
                {"message_id": "msg3", "quote": "Alice and Charlie collaborating"},
            ],
            "confidence": 0.85,
        },
        {
            "claim_id": "claim:003",
            "claim_type": "works_with",
            "subject_id": "person:bob",
            "object_id": "person:charlie",
            "subject_name": "Bob Jones",
            "object_name": "Charlie Brown",
            "description": "Bob Jones works_with Charlie Brown",
            "evidence": [
                {"message_id": "msg4", "quote": "Bob working with Charlie"},
            ],
            "confidence": 0.90,
        },
    ]


def make_test_resolution_map():
    return {
        "Alice Smith": "person:alice",
        "A. Smith": "person:alice",
        "Bob Jones": "person:bob",
    }


# ---------------------------------------------------------------------------
# Soft delete entity
# ---------------------------------------------------------------------------

class TestSoftDeleteEntity:
    def test_entity_marked_deleted(self):
        entities = make_test_entities()
        claims = make_test_claims()
        manager = RedactionManager(entities, claims, {})

        record = manager.soft_delete_entity("person:alice", "privacy_request")

        assert record is not None
        assert entities["person:alice"]["is_deleted"] is True
        assert entities["person:alice"]["deleted_at"] is not None
        assert entities["person:alice"]["deletion_reason"] == "privacy_request"

    def test_cascades_to_claims_as_subject(self):
        entities = make_test_entities()
        claims = make_test_claims()
        manager = RedactionManager(entities, claims, {})

        manager.soft_delete_entity("person:alice", "test")

        # claim:001 has alice as subject → deleted
        assert claims[0]["is_deleted"] is True
        # claim:002 has alice as subject → deleted
        assert claims[1]["is_deleted"] is True
        # claim:003 has bob as subject, not alice → NOT deleted
        assert claims[2].get("is_deleted") is not True

    def test_cascades_to_claims_as_object(self):
        entities = make_test_entities()
        claims = make_test_claims()
        manager = RedactionManager(entities, claims, {})

        manager.soft_delete_entity("person:bob", "test")

        # claim:001 has bob as object → deleted
        assert claims[0]["is_deleted"] is True
        # claim:003 has bob as subject → deleted
        assert claims[2]["is_deleted"] is True
        # claim:002 has no bob → NOT deleted
        assert claims[1].get("is_deleted") is not True

    def test_evidence_marked_deleted(self):
        entities = make_test_entities()
        claims = make_test_claims()
        manager = RedactionManager(entities, claims, {})

        manager.soft_delete_entity("person:alice", "test")

        for ev in claims[0]["evidence"]:
            assert ev["is_deleted"] is True

    def test_deletion_record_created(self):
        entities = make_test_entities()
        claims = make_test_claims()
        manager = RedactionManager(entities, claims, {})

        record = manager.soft_delete_entity("person:alice", "privacy")

        assert record.target_type == "entity"
        assert record.target_id == "person:alice"
        assert record.action == "soft_delete"
        assert record.reason == "privacy"
        assert len(record.cascaded_claim_ids) == 2  # claims 001 and 002

    def test_already_deleted_returns_none(self):
        entities = make_test_entities()
        manager = RedactionManager(entities, [], {})

        manager.soft_delete_entity("person:alice", "first")
        result = manager.soft_delete_entity("person:alice", "second")
        assert result is None

    def test_nonexistent_entity_returns_none(self):
        manager = RedactionManager({}, [], {})
        result = manager.soft_delete_entity("person:nobody", "test")
        assert result is None

    def test_bob_entity_not_affected(self):
        """Deleting alice should not affect bob's entity flags."""
        entities = make_test_entities()
        claims = make_test_claims()
        manager = RedactionManager(entities, claims, {})

        manager.soft_delete_entity("person:alice", "test")

        assert entities["person:bob"].get("is_deleted") is not True


# ---------------------------------------------------------------------------
# Soft delete claim
# ---------------------------------------------------------------------------

class TestSoftDeleteClaim:
    def test_claim_marked_deleted(self):
        claims = make_test_claims()
        manager = RedactionManager({}, claims, {})

        record = manager.soft_delete_claim("claim:001", "bad_extraction")

        assert claims[0]["is_deleted"] is True
        assert claims[0]["deletion_reason"] == "bad_extraction"
        assert record.target_type == "claim"

    def test_does_not_delete_entities(self):
        """Deleting one claim should not delete the connected entities."""
        entities = make_test_entities()
        claims = make_test_claims()
        manager = RedactionManager(entities, claims, {})

        manager.soft_delete_claim("claim:001", "test")

        assert entities["person:alice"].get("is_deleted") is not True
        assert entities["person:bob"].get("is_deleted") is not True

    def test_does_not_delete_other_claims(self):
        claims = make_test_claims()
        manager = RedactionManager({}, claims, {})

        manager.soft_delete_claim("claim:001", "test")

        assert claims[1].get("is_deleted") is not True
        assert claims[2].get("is_deleted") is not True

    def test_nonexistent_claim_returns_none(self):
        manager = RedactionManager({}, [], {})
        assert manager.soft_delete_claim("claim:999", "test") is None


# ---------------------------------------------------------------------------
# Redact entity
# ---------------------------------------------------------------------------

class TestRedactEntity:
    def test_content_replaced(self):
        entities = make_test_entities()
        claims = make_test_claims()
        manager = RedactionManager(entities, claims, {})

        manager.redact_entity("person:alice", "legal")

        assert entities["person:alice"]["canonical_name"] == REDACTED_PLACEHOLDER
        assert entities["person:alice"]["aliases"] == [REDACTED_PLACEHOLDER]
        assert entities["person:alice"]["emails"] == []

    def test_evidence_quotes_replaced(self):
        entities = make_test_entities()
        claims = make_test_claims()
        manager = RedactionManager(entities, claims, {})

        manager.redact_entity("person:alice", "legal")

        # claim:001 has alice as subject — evidence should be redacted
        for ev in claims[0]["evidence"]:
            assert ev["quote"] == REDACTED_PLACEHOLDER

    def test_claim_names_replaced(self):
        entities = make_test_entities()
        claims = make_test_claims()
        manager = RedactionManager(entities, claims, {})

        manager.redact_entity("person:alice", "legal")

        # claim:001 — alice is subject
        assert claims[0]["subject_name"] == REDACTED_PLACEHOLDER
        assert claims[0]["description"] == REDACTED_PLACEHOLDER

    def test_resolution_map_updated(self):
        entities = make_test_entities()
        res_map = make_test_resolution_map()
        manager = RedactionManager(entities, [], res_map)

        manager.redact_entity("person:alice", "legal")

        assert res_map["Alice Smith"].startswith("REDACTED:")
        assert res_map["A. Smith"].startswith("REDACTED:")
        # Bob's entry unchanged
        assert res_map["Bob Jones"] == "person:bob"

    def test_deletion_record_action_is_redact(self):
        entities = make_test_entities()
        manager = RedactionManager(entities, [], {})

        record = manager.redact_entity("person:alice", "legal")
        assert record.action == "redact"


# ---------------------------------------------------------------------------
# Restore entity
# ---------------------------------------------------------------------------

class TestRestoreEntity:
    def test_restore_soft_deleted_entity(self):
        entities = make_test_entities()
        claims = make_test_claims()
        manager = RedactionManager(entities, claims, {})

        manager.soft_delete_entity("person:alice", "test")
        assert entities["person:alice"]["is_deleted"] is True

        result = manager.restore_entity("person:alice")
        assert result is True
        assert entities["person:alice"]["is_deleted"] is False
        assert "deleted_at" not in entities["person:alice"]

    def test_restore_cascaded_claims(self):
        entities = make_test_entities()
        claims = make_test_claims()
        manager = RedactionManager(entities, claims, {})

        manager.soft_delete_entity("person:alice", "test")
        manager.restore_entity("person:alice")

        # Cascaded claims should also be restored
        assert claims[0].get("is_deleted") is not True
        assert claims[1].get("is_deleted") is not True

    def test_restore_evidence(self):
        entities = make_test_entities()
        claims = make_test_claims()
        manager = RedactionManager(entities, claims, {})

        manager.soft_delete_entity("person:alice", "test")
        manager.restore_entity("person:alice")

        for ev in claims[0]["evidence"]:
            assert "is_deleted" not in ev

    def test_cannot_restore_redacted(self):
        entities = make_test_entities()
        manager = RedactionManager(entities, [], {})

        manager.redact_entity("person:alice", "legal")
        result = manager.restore_entity("person:alice")
        assert result is False

    def test_cannot_restore_non_deleted(self):
        entities = make_test_entities()
        manager = RedactionManager(entities, [], {})

        result = manager.restore_entity("person:alice")
        assert result is False

    def test_deletion_record_marked_restored(self):
        entities = make_test_entities()
        manager = RedactionManager(entities, [], {})

        manager.soft_delete_entity("person:alice", "test")
        manager.restore_entity("person:alice")

        log = manager.get_deletion_log()
        assert log[0]["status"] == "restored"


# ---------------------------------------------------------------------------
# Restore claim
# ---------------------------------------------------------------------------

class TestRestoreClaim:
    def test_restore_soft_deleted_claim(self):
        claims = make_test_claims()
        manager = RedactionManager({}, claims, {})

        manager.soft_delete_claim("claim:001", "test")
        result = manager.restore_claim("claim:001")

        assert result is True
        assert claims[0].get("is_deleted") is not True

    def test_cannot_restore_redacted_claim(self):
        entities = make_test_entities()
        claims = make_test_claims()
        manager = RedactionManager(entities, claims, {})

        manager.redact_entity("person:alice", "legal")
        result = manager.restore_claim("claim:001")
        assert result is False


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

class TestQueryHelpers:
    def test_active_entities_excludes_deleted(self):
        entities = make_test_entities()
        manager = RedactionManager(entities, [], {})

        manager.soft_delete_entity("person:alice", "test")

        active = manager.get_active_entities()
        assert "person:alice" not in active
        assert "person:bob" in active

    def test_active_claims_excludes_deleted(self):
        claims = make_test_claims()
        manager = RedactionManager({}, claims, {})

        manager.soft_delete_claim("claim:001", "test")

        active = manager.get_active_claims()
        assert len(active) == 2
        assert all(c["claim_id"] != "claim:001" for c in active)

    def test_deleted_entities_only_deleted(self):
        entities = make_test_entities()
        manager = RedactionManager(entities, [], {})

        manager.soft_delete_entity("person:alice", "test")

        deleted = manager.get_deleted_entities()
        assert "person:alice" in deleted
        assert "person:bob" not in deleted

    def test_stats(self):
        entities = make_test_entities()
        claims = make_test_claims()
        manager = RedactionManager(entities, claims, {})

        manager.soft_delete_entity("person:alice", "test")

        stats = manager.get_stats()
        assert stats["total_deleted_entities"] == 1
        assert stats["total_active_entities"] == 1
        assert stats["total_deleted_claims"] == 2  # cascaded
        assert stats["total_active_claims"] == 1
        assert stats["deletion_operations"] == 1