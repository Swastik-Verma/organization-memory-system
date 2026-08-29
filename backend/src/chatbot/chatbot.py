"""
RAG Chatbot — generates cited natural language answers.

Takes a ContextPack from the retrieval engine and produces a human-readable
answer with inline citations that map back to specific evidence items.

Pipeline:
  1. Check if context is empty → return canned "no info" response
  2. Format ContextPack claims into numbered text the LLM can reference
  3. Build the full prompt: system prompt + formatted context + question
  4. Call Gemini to generate an answer with [N] citation markers
  5. Parse [N] markers from the response and map each to evidence metadata
  6. Return the answer text + structured citation list

Design decisions:
  - Uses the same Gemini client pattern as QueryUnderstanding (Day 30)
  - thinking_budget=0 because the LLM's job is synthesis, not reasoning
  - Temperature=0.3 (slight creativity for natural prose, but mostly faithful)
  - Unix timestamps from semantic path are converted to ISO dates before
    being shown to the LLM, fixing the Day 31 cosmetic issue
  - Citation parsing uses regex; invalid markers (referencing non-existent
    context items) are logged and dropped rather than crashing
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig

from src.chatbot.prompts import (
    CLARIFICATION_PREFIX,
    NO_CONTEXT_RESPONSE,
    SYSTEM_PROMPT,
)

# Load .env from project root (same pattern as query_understanding.py)
_project_root = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_project_root / ".env")

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Data classes for chatbot output
# ------------------------------------------------------------------ #

@dataclass
class Citation:
    """One resolved citation in the chatbot's answer."""
    marker: str              # "[1]", "[2]", etc.
    index: int               # 1, 2, etc. (the number inside brackets)
    claim_id: str = ""       # ID of the claim this cites
    claim_type: str = ""     # reports_to, works_with, etc.
    subject_name: str = ""   # who the claim is about
    object_name: str = ""    # the other party
    evidence_quote: str = "" # the verbatim evidence text
    evidence_id: str = ""    # evidence node ID (for frontend linking)
    confidence: float = 0.0  # claim confidence


@dataclass
class ChatbotResponse:
    """The complete chatbot output."""
    answer: str                           # the generated natural language answer
    citations: list[Citation] = field(default_factory=list)
    has_clarification: bool = False       # was a clarification note included?
    context_items_used: int = 0           # how many context items were provided
    generation_model: str = ""            # which model generated this


# ------------------------------------------------------------------ #
# Main class
# ------------------------------------------------------------------ #

class Chatbot:
    """Generates cited natural language answers from retrieved context."""

    def __init__(self, gemini_model: str = "gemini-2.5-flash"):
        """
        Args:
            gemini_model: Gemini model for answer generation.
                          Using gemini-2.5-flash (not flash-lite) because
                          answer generation needs better language quality
                          than the parsing tasks in query_understanding.
        """
        self.model_name = gemini_model

        # Initialize Gemini client (same pattern as QueryUnderstanding)
        self.client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY", ""),
        )

        logger.info("Chatbot initialized — model=%s", self.model_name)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def generate_answer(
        self,
        question: str,
        context_pack,          # ContextPack from retrieval_engine
        context_text: str,     # pre-formatted text from format_context_for_llm
    ) -> ChatbotResponse:
        """
        Generate a cited natural language answer.

        Args:
            question: the user's original question
            context_pack: the ContextPack from RetrievalEngine.retrieve()
            context_text: formatted context from format_context_for_llm()

        Returns:
            ChatbotResponse with answer text and resolved citations
        """
        # Step 1: Check for empty context
        if not context_pack.claims:
            return ChatbotResponse(
                answer=NO_CONTEXT_RESPONSE,
                citations=[],
                has_clarification=bool(context_pack.clarification),
                context_items_used=0,
                generation_model=self.model_name,
            )

        # Step 2: Build the context-to-citation mapping
        # This maps [1], [2], ... to the actual claim/evidence data
        citation_map = self._build_citation_map(context_pack)

        # Step 3: Format the context text, fixing Unix timestamps
        clean_context = self._clean_context_text(context_text)

        # step 4 was deleted from here so after step 3 to step 5 is not a mistake

        # Step 5: Call the LLM
        raw_answer = self._call_llm(question, clean_context)

        # Step 6: Parse citations from the answer
        citations = self._parse_citations(raw_answer, citation_map)

     
        logger.info(
            "Generated answer: %d chars, %d citations, model=%s",
            len(raw_answer),
            len(citations),
            self.model_name,
        )

        return ChatbotResponse(
            answer=raw_answer,
            citations=citations,
            has_clarification=bool(context_pack.clarification),
            context_items_used=len(context_pack.claims),
            generation_model=self.model_name,
        )

    # ------------------------------------------------------------------ #
    # Step 2: Build citation map
    # ------------------------------------------------------------------ #

    def _build_citation_map(self, context_pack) -> dict[int, Citation]:
        """
        Build a mapping from context item number to Citation metadata.

        The context text numbers claims as [1], [2], ... in order.
        This map lets us resolve those markers to actual evidence data.
        """
        citation_map: dict[int, Citation] = {}

        for i, claim in enumerate(context_pack.claims, start=1):
            # Get the first evidence quote if available
            evidence_quote = ""
            evidence_id = ""
            if claim.evidence:
                first_ev = claim.evidence[0]
                evidence_quote = first_ev.get("quote", "")
                evidence_id = first_ev.get("evidence_id", "")

            citation_map[i] = Citation(
                marker=f"[{i}]",
                index=i,
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                subject_name=claim.subject_name,
                object_name=claim.object_name,
                evidence_quote=evidence_quote,
                evidence_id=evidence_id,
                confidence=claim.confidence,
            )

        return citation_map

    # ------------------------------------------------------------------ #
    # Step 3: Clean context text (fix Unix timestamps)
    # ------------------------------------------------------------------ #

    def _clean_context_text(self, context_text: str) -> str:
        """
        Fix Unix timestamps in the context text before sending to LLM.

        The semantic retrieval path stores valid_from/valid_to as Unix
        timestamps in Qdrant (e.g. 968371200). format_context_for_llm()
        passes these through as-is. We convert them to readable dates
        here so the LLM sees "2000-09-08" instead of "968371200".
        """
        def replace_timestamp(match):
            """Regex replacement function for Unix timestamp patterns."""
            prefix = match.group(1)   # "Valid from: " or "Valid to: "
            value = match.group(2)    # the number string
            try:
                ts = float(value)
                # Sanity check: Enron-era timestamps are 8.5e8 to 1.0e9
                if 8e8 < ts < 1.1e9:
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                    return f"{prefix}{dt.strftime('%Y-%m-%d')}"
            except (ValueError, OverflowError, OSError):
                pass
            # If conversion fails, return unchanged
            return match.group(0)

        # Pattern: "Valid from: 968371200" or "Valid to: 993081600"
        cleaned = re.sub(
            r"(Valid (?:from|to): )(\d{9,10})",
            replace_timestamp,
            context_text,
        )

        return cleaned

    # ------------------------------------------------------------------ #
    # Step 5: Call the LLM
    # ------------------------------------------------------------------ #

    def _call_llm(self, question: str, context_text: str) -> str:
        """
        Call Gemini to generate a cited answer.

        The prompt structure:
          - System instruction: SYSTEM_PROMPT (grounding rules)
          - User message: CONTEXT block + QUESTION

        Temperature 0.3: enough variation for natural prose, but
        mostly deterministic to stay faithful to the context.
        """
        user_message = f"""CONTEXT:
{context_text}

QUESTION: {question}

Answer the question using ONLY the context above. Cite every factual claim with [N] markers referring to the numbered context items."""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_message,
                config=GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.3,
                    thinking_config=ThinkingConfig(thinking_level="low"),
                ),
            )

            answer = response.text.strip()
            logger.debug("Raw LLM answer: %s", answer[:200])
            return answer

        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            return (
                "I encountered an error while generating an answer. "
                "The retrieved context is available in the claims section "
                "of this response. Please try again."
            )

    # ------------------------------------------------------------------ #
    # Step 7: Parse citations
    # ------------------------------------------------------------------ #

    def _parse_citations(
        self,
        answer: str,
        citation_map: dict[int, Citation],
    ) -> list[Citation]:
        """
        Extract [N] citation markers from the answer and resolve them.

        Finds all [N] patterns in the text, looks up each N in the
        citation_map, and returns a deduplicated list of resolved
        Citation objects. Invalid markers (N not in map) are logged
        and dropped.
        """
        # Find all [N] patterns — match single or multi-digit numbers
        marker_pattern = re.compile(r"\[(\d+)\]")
        found_indices: list[int] = []

        for match in marker_pattern.finditer(answer):
            idx = int(match.group(1))
            if idx not in found_indices:
                found_indices.append(idx)

        # Resolve each marker
        citations: list[Citation] = []
        invalid_count = 0

        for idx in found_indices:
            if idx in citation_map:
                citations.append(citation_map[idx])
            else:
                invalid_count += 1
                logger.warning(
                    "Citation [%d] in answer but not in context "
                    "(context has %d items)",
                    idx,
                    len(citation_map),
                )

        if invalid_count > 0:
            logger.warning(
                "%d invalid citation(s) found in LLM answer", invalid_count
            )

        return citations