"""Tests for the Qdrant vector index module."""

import pytest
from unittest.mock import MagicMock, patch
from src.retrieval.qdrant_index import QdrantIndex, _string_to_point_id


class TestStringToPointId:
    """Test the ID hashing function."""

    def test_deterministic(self):
        """Same input always produces same ID."""
        id1 = _string_to_point_id("evidence:abc123")
        id2 = _string_to_point_id("evidence:abc123")
        assert id1 == id2

    def test_different_inputs(self):
        """Different inputs produce different IDs."""
        id1 = _string_to_point_id("evidence:abc123")
        id2 = _string_to_point_id("evidence:def456")
        assert id1 != id2

    def test_positive_integer(self):
        """All IDs are positive."""
        for i in range(100):
            pid = _string_to_point_id(f"evidence:test{i}")
            assert pid > 0

    def test_fits_in_64bit(self):
        """IDs fit in a 64-bit signed integer."""
        for i in range(100):
            pid = _string_to_point_id(f"evidence:test{i}")
            assert pid < 2**63


class TestQdrantIndexUnit:
    """Unit tests using mocked Qdrant client."""

    @patch("src.retrieval.qdrant_index.SentenceTransformer")
    @patch("src.retrieval.qdrant_index.QdrantClient")
    def test_embed_texts(self, mock_client_cls, mock_model_cls):
        """Embedding produces correct-dimension vectors."""
        import numpy as np

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(3, 384)
        mock_model_cls.return_value = mock_model

        index = QdrantIndex()
        vectors = index.embed_texts(["text one", "text two", "text three"])

        assert len(vectors) == 3
        assert len(vectors[0]) == 384
        mock_model.encode.assert_called_once()

    @patch("src.retrieval.qdrant_index.SentenceTransformer")
    @patch("src.retrieval.qdrant_index.QdrantClient")
    def test_upsert_skips_empty_quotes(self, mock_client_cls, mock_model_cls):
        """Records with empty quotes are filtered out."""
        mock_model = MagicMock()
        mock_model_cls.return_value = mock_model

        index = QdrantIndex()
        count = index.upsert_evidence([
            {"evidence_id": "e1", "quote": "", "claim_id": "c1"},
            {"evidence_id": "e2", "quote": "   ", "claim_id": "c2"},
        ])

        assert count == 0
        mock_model.encode.assert_not_called()

    @patch("src.retrieval.qdrant_index.SentenceTransformer")
    @patch("src.retrieval.qdrant_index.QdrantClient")
    def test_upsert_empty_list(self, mock_client_cls, mock_model_cls):
        """Empty input returns 0."""
        mock_model_cls.return_value = MagicMock()
        index = QdrantIndex()
        assert index.upsert_evidence([]) == 0