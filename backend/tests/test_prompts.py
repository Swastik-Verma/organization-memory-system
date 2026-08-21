"""Sanity tests for extraction prompts."""
from src.extraction.prompts import EXTRACTION_INSTRUCTIONS  


class TestPrompts:
    def test_prompt_exists_and_nonempty(self):
        assert EXTRACTION_INSTRUCTIONS is not None
        assert len(EXTRACTION_INSTRUCTIONS) > 100  # should be a substantial prompt
    
    def test_prompt_mentions_verbatim(self):
        """v2 prompt requires verbatim evidence."""
        prompt_lower = EXTRACTION_INSTRUCTIONS.lower()
        assert "verbatim" in prompt_lower or "exact quote" in prompt_lower
    
    def test_prompt_has_closed_vocabulary(self):
        """v2 prompt defines the 5 relationship types."""
        assert "reports_to" in EXTRACTION_INSTRUCTIONS
        assert "works_with" in EXTRACTION_INSTRUCTIONS
        assert "requests_from" in EXTRACTION_INSTRUCTIONS
        assert "negotiating_with" in EXTRACTION_INSTRUCTIONS
        assert "informs" in EXTRACTION_INSTRUCTIONS