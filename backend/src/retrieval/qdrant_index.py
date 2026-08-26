"""
Vector index for semantic search over evidence excerpts.

Uses Qdrant for vector storage and sentence-transformers for embedding.
Metadata stored alongside each vector enables filtered search
(by access_level, confidence, date range, entity, claim).
"""

import logging
from datetime import datetime
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    Range,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

COLLECTION_NAME = "evidence"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
BATCH_SIZE = 256


def _date_to_timestamp(date_str):
    if date_str is None:
        return None
    try:
        return int(datetime.fromisoformat(str(date_str)).timestamp())
    except:
        return None


class QdrantIndex:
    """Manages the Qdrant vector collection for evidence excerpts."""

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        collection_name: str = COLLECTION_NAME,
    ):
        self.client = QdrantClient(url=qdrant_url)
        self.collection_name = collection_name
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info(
            "QdrantIndex initialized — model=%s, dim=%d, collection=%s",
            EMBEDDING_MODEL,
            EMBEDDING_DIM,
            collection_name,
        )

    # ------------------------------------------------------------------ #
    # Collection management
    # ------------------------------------------------------------------ #

    def create_collection(self, recreate: bool = False) -> None:
        """Create the Qdrant collection. If recreate=True, drops existing."""
        collections = [
            c.name for c in self.client.get_collections().collections
        ]

        if self.collection_name in collections:
            if recreate:
                logger.warning("Dropping existing collection '%s'", self.collection_name)
                self.client.delete_collection(self.collection_name)
            else:
                logger.info("Collection '%s' already exists, skipping creation", self.collection_name)
                self._ensure_payload_indexes()
                return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.COSINE,
            ),
        )
        logger.info("Created collection '%s'", self.collection_name)
        self._ensure_payload_indexes()

    def _ensure_payload_indexes(self) -> None:
        """Create payload indexes for filtered search performance."""
        index_fields = {
            "access_level": PayloadSchemaType.INTEGER,
            "confidence": PayloadSchemaType.FLOAT,
            "claim_type": PayloadSchemaType.KEYWORD,
            "valid_from": PayloadSchemaType.FLOAT,  # ISO date string
            "is_deleted": PayloadSchemaType.BOOL,
        }
        for field_name, schema_type in index_fields.items():
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=schema_type,
                )
            except Exception:
                # Index may already exist — that's fine
                pass

    # ------------------------------------------------------------------ #
    # Embedding
    # ------------------------------------------------------------------ #

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of 384-dim vectors."""
        return self.model.encode(
            texts,
            show_progress_bar=False,
            batch_size=BATCH_SIZE,
        ).tolist()

    # ------------------------------------------------------------------ #
    # Upsert
    # ------------------------------------------------------------------ #

    def upsert_evidence(self, evidence_records: list[dict]) -> int:
        """
        Embed and upsert evidence records into Qdrant.

        Each record must have:
            evidence_id: str         — used as the Qdrant point ID (hashed to int)
            quote: str               — the text to embed
            claim_id: str
            claim_type: str
            subject_id: str
            object_id: str
            confidence: float
            access_level: int
            valid_from: str | None   — ISO date or None
            message_id: str
            is_deleted: bool
        """
        if not evidence_records:
            return 0

        # Filter out empty quotes — nothing to embed
        records = [r for r in evidence_records if r.get("quote", "").strip()]
        if not records:
            return 0

        texts = [r["quote"] for r in records]
        embeddings = self.embed_texts(texts)

        points = []
        for record, vector in zip(records, embeddings):
            # Qdrant needs integer or UUID point IDs.
            # Our evidence_id is a string like "evidence:abc123".
            # Hash it to a stable positive integer.
            point_id = _string_to_point_id(record["evidence_id"])

            payload = {
                "evidence_id": record["evidence_id"],
                "quote": record["quote"],
                "claim_id": record["claim_id"],
                "claim_type": record.get("claim_type", ""),
                "subject_id": record.get("subject_id", ""),
                "object_id": record.get("object_id", ""),
                "subject_name": record.get("subject_name", ""),
                "object_name": record.get("object_name", ""),
                "confidence": record.get("confidence", 0.0),
                "access_level": record.get("access_level", 1),
                "valid_from": _date_to_timestamp(record.get("valid_from")),#record.get("valid_from"),  # None OK
                "valid_to": _date_to_timestamp(record.get("valid_to")),#record.get("valid_to"),
                "status": record.get("status", ""),
                "mention_count": record.get("mention_count", 0),
                "message_id": record.get("message_id", ""),
                "is_deleted": record.get("is_deleted", False),
            }
            points.append(PointStruct(id=point_id, vector=vector, payload=payload))

        # Upsert in batches
        upserted = 0
        for i in range(0, len(points), BATCH_SIZE):
            batch = points[i : i + BATCH_SIZE]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )
            upserted += len(batch)
            logger.info("Upserted %d / %d points", upserted, len(points))

        return upserted

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #

    def semantic_search(
        self,
        query: str,
        top_k: int = 10,
        max_access_level: int = 4,
        min_confidence: float = 0.0,
        claim_type: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> list[dict]:
        """
        Semantic search with metadata filtering.

        Filters:
            max_access_level — permission ceiling (user's clearance)
            min_confidence   — quality floor
            claim_type       — e.g. "reports_to", "works_at"
            date_from/to     — ISO date strings for temporal window
            entity_id        — matches subject_id OR object_id

        Returns list of dicts with: evidence_id, quote, score,
        claim_id, claim_type, subject_id, object_id, confidence,
        access_level, valid_from, message_id.
        """
        query_vector = self.model.encode(query).tolist()

        # Build filter conditions
        must_conditions = [
            # Always exclude deleted
            FieldCondition(key="is_deleted", match=MatchValue(value=False)),
            # Permission filter — never return above user's clearance
            FieldCondition(
                key="access_level",
                range=Range(lte=max_access_level),
            ),
        ]

        if min_confidence > 0:
            must_conditions.append(
                FieldCondition(
                    key="confidence",
                    range=Range(gte=min_confidence),
                )
            )

        if claim_type:
            must_conditions.append(
                FieldCondition(key="claim_type", match=MatchValue(value=claim_type)),
            )

        if date_from:
            ts = _date_to_timestamp(date_from)
            if ts:
                must_conditions.append(
                    FieldCondition(key="valid_from", range=Range(gte=ts)),
                )

        if date_to:
            ts = _date_to_timestamp(date_to)
            if ts:
                must_conditions.append(
                    FieldCondition(key="valid_from", range=Range(lte=ts)),
                )

        # Entity filter — should match either subject or object
        # Qdrant doesn't have native OR on two fields, so we use
        # a "should" condition with min_should_match
        should_conditions = []
        if entity_id:
            should_conditions = [
                FieldCondition(key="subject_id", match=MatchValue(value=entity_id)),
                FieldCondition(key="object_id", match=MatchValue(value=entity_id)),
            ]

        if should_conditions:
            search_filter = Filter(
                must=must_conditions,
                should=should_conditions,
                # min_should=MinShould(min_count = 1),
                # min_should not needed — Qdrant requires at least 1 by default
            )
        else:
            search_filter = Filter(
                must=must_conditions,
            )

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=search_filter,
            limit=top_k,
            with_payload=True,
        )

        return [
            {
                "evidence_id": hit.payload.get("evidence_id"),
                "quote": hit.payload.get("quote"),
                "score": hit.score,
                "claim_id": hit.payload.get("claim_id"),
                "claim_type": hit.payload.get("claim_type"),
                "subject_id": hit.payload.get("subject_id"),
                "object_id": hit.payload.get("object_id"),
                "confidence": hit.payload.get("confidence"),
                "access_level": hit.payload.get("access_level"),
                "valid_from": hit.payload.get("valid_from"),
                "message_id": hit.payload.get("message_id"),
            }
            for hit in results.points
        ]

    # ------------------------------------------------------------------ #
    # Deletion support (for soft-delete integration)
    # ------------------------------------------------------------------ #

    def mark_deleted(self, evidence_ids: list[str]) -> int:
        """Mark evidence points as deleted (sets is_deleted=True in payload)."""
        point_ids = [_string_to_point_id(eid) for eid in evidence_ids]

        self.client.set_payload(
            collection_name=self.collection_name,
            payload={"is_deleted": True},
            points=point_ids,
        )
        return len(point_ids)

    def hard_delete(self, evidence_ids: list[str]) -> int:
        """Permanently remove points from the collection."""
        point_ids = [_string_to_point_id(eid) for eid in evidence_ids]

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="evidence_id",
                            match=MatchValue(value=eid),
                        )
                    ]
                )
            ),
        )
        return len(point_ids)

    def get_collection_info(self) -> dict:
        """Return collection stats."""
        info = self.client.get_collection(self.collection_name)
        return {
            "name": self.collection_name,
            "points_count": info.points_count,
            "status": info.status.value,
        }


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _string_to_point_id(s: str) -> int:
    """Convert a string ID to a stable positive integer for Qdrant."""
    if not s:
        raise ValueError(f"Cannot hash None/empty string to point ID")
    import hashlib
    return int(hashlib.sha256(s.encode()).hexdigest()[:15], 16)