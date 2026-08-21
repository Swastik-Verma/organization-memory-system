import pytest
from src.extraction.version_manager import (
    compute_prompt_hash,
    get_current_version,
    stamp_extraction,
)


class TestPromptHash:
    def test_deterministic(self):
        """Same prompt always produces the same hash"""
        h1 = compute_prompt_hash("You are an expert analyst")
        h2 = compute_prompt_hash("You are an expert analyst")
        assert h1 == h2

    def test_different_prompts_different_hash(self):
        h1 = compute_prompt_hash("You are an expert analyst")
        h2 = compute_prompt_hash("You are an expert researcher")
        assert h1 != h2

    def test_hash_length(self):
        h = compute_prompt_hash("test prompt")
        assert len(h) == 12

    def test_hash_is_hex(self):
        h = compute_prompt_hash("test prompt")
        # Should only contain hex characters
        assert all(c in "0123456789abcdef" for c in h)

    def test_whitespace_sensitive(self):
        """Even whitespace changes should produce different hashes"""
        h1 = compute_prompt_hash("hello world")
        h2 = compute_prompt_hash("hello  world")
        assert h1 != h2


class TestStampExtraction:
    def test_adds_version_fields(self):
        extraction = {"message_id": "test@enron.com", "people": []}
        stamped = stamp_extraction(extraction, "some prompt", "gemini-3.1-flash-lite")
        assert "prompt_version" in stamped
        assert stamped["model_name"] == "gemini-3.1-flash-lite"
        assert len(stamped["prompt_version"]) == 12

    def test_preserves_existing_data(self):
        extraction = {
            "message_id": "test@enron.com",
            "people": [{"name": "John"}],
            "confidence": 0.9,
        }
        stamped = stamp_extraction(extraction, "prompt", "model")
        assert stamped["people"] == [{"name": "John"}]
        assert stamped["confidence"] == 0.9

    def test_overwrites_old_version(self):
        extraction = {
            "message_id": "test@enron.com",
            "prompt_version": "old_hash_123",
            "model_name": "old-model",
        }
        stamped = stamp_extraction(extraction, "new prompt", "new-model")
        assert stamped["prompt_version"] != "old_hash_123"
        assert stamped["model_name"] == "new-model"


class TestGetCurrentVersion:
    def test_returns_both_fields(self):
        version = get_current_version("my prompt", "gemini-3.1-flash-lite")
        assert "prompt_version" in version
        assert "model_name" in version
        assert version["model_name"] == "gemini-3.1-flash-lite"