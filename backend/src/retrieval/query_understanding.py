"""
Query understanding layer — parses natural language questions
into structured retrieval plans.

Sits between the user's raw question and the retrieval engine (Day 31).
Uses Gemini to extract mentioned entities, question type, time constraints,
and ambiguity signals. Resolves entity names to canonical graph IDs via
find_entity() from the temporal query engine (Day 24).

The output is a QueryPlan dataclass that tells the retrieval engine
exactly what kind of retrieval to perform.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_project_root / ".env")

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Data classes — the structured output of query understanding
# ------------------------------------------------------------------ #

class QuestionType(str, Enum):
    """What kind of answer the user is looking for."""
    WHO = "who"              # asks about a person / people
    WHAT = "what"            # asks about a fact, event, or concept
    WHEN = "when"            # asks about timing
    WHY = "why"              # asks about reasoning / motivation
    HISTORY = "history"      # asks for chronological record
    CURRENT = "current"      # asks for present-state facts
    COMPARISON = "comparison" # asks to compare two entities / time periods
    LIST = "list"            # asks for enumeration ("list all...", "who are...")
    YES_NO = "yes_no"        # asks a binary question


class TimeConstraintType(str, Enum):
    """How the time reference should be applied."""
    POINT = "point"          # "in March 2001" — single date
    RANGE = "range"          # "between 2000 and 2001" — date range
    BEFORE = "before"        # "before the restructuring" — upper bound
    AFTER = "after"          # "after January 2001" — lower bound
    NONE = "none"            # no time reference


class RetrievalStrategy(str, Enum):
    """Which retrieval path(s) the retrieval engine should use."""
    GRAPH = "graph"          # entity-based, use temporal_queries.py
    SEMANTIC = "semantic"    # concept-based, use Qdrant
    HYBRID = "hybrid"        # both graph + semantic, merge results


@dataclass
class ResolvedEntity:
    """An entity mentioned in the query, resolved to a canonical graph ID."""
    raw_name: str                    # what the user typed
    canonical_id: Optional[str]      # graph ID, or None if not found
    canonical_name: Optional[str]    # display name from graph
    entity_type: Optional[str]       # "person" or "organization"
    confidence: float                # how confident the resolution is
    alternatives: list[dict] = field(default_factory=list)
    # ^ other possible matches (for ambiguity)


@dataclass
class TimeConstraint:
    """Temporal filter extracted from the query."""
    constraint_type: TimeConstraintType
    date_from: Optional[str] = None   # ISO date string
    date_to: Optional[str] = None     # ISO date string
    raw_reference: Optional[str] = None  # original text ("March 2001")


@dataclass
class QueryPlan:
    """The structured output of query understanding.

    This is what the retrieval engine (Day 31) consumes.
    """
    raw_query: str                    # original user question
    question_type: QuestionType
    entities: list[ResolvedEntity]    # resolved entity references
    time_constraint: TimeConstraint
    retrieval_strategy: RetrievalStrategy
    claim_types: list[str]            # if specific types are relevant
    needs_clarification: bool         # should we ask the user to clarify?
    clarification_reason: Optional[str] = None
    semantic_query: Optional[str] = None
    # ^ reformulated query for Qdrant (may differ from raw_query)


# ------------------------------------------------------------------ #
# LLM prompt for question parsing
# ------------------------------------------------------------------ #

QUERY_PARSE_PROMPT = """You are a query parser for an organizational memory system built from the Enron email corpus.

Your job: analyze the user's question and extract structured information.
The system has a Neo4j knowledge graph with these entity types: Person, Organization, Deal, Decision.
Claims (relationships) between entities include: reports_to, works_at, works_with, manages, knows.

Given a user question, respond with ONLY a JSON object (no markdown, no backticks, no explanation):

{
  "mentioned_entities": [
    {
      "name": "the entity name as the user wrote it",
      "type": "person or organization or deal or decision or unknown"
    }
  ],
  "question_type": "who | what | when | why | history | current | comparison | list | yes_no",
  "time_reference": {
    "type": "point | range | before | after | none",
    "date_from": "YYYY-MM-DD or null",
    "date_to": "YYYY-MM-DD or null",
    "raw_text": "the original time reference text or null"
  },
  "is_ambiguous": true/false,
  "ambiguity_reason": "why it's ambiguous, or null",
  "claim_types": ["reports_to", "works_at", ...] or [],
  "semantic_keywords": "reformulated search query for concept-based retrieval, or null"
}

Rules:
1. Extract ALL entity names mentioned. Use the name form the user gave.
2. For time references, convert to dates when possible. The Enron corpus covers 1997-2001.
   - "in 2001" → point, date_from = "2001-01-01"
   - "March 2001" → point, date_from = "2001-03-01"
   - "between 2000 and 2001" → range, date_from = "2000-01-01", date_to = "2001-12-31"
   - "before the collapse" → before, date_to = "2001-12-01" (Enron collapsed Dec 2001)
   - No time reference → none
3. A question is ambiguous when:
   - A common name is used without enough context (just "Smith")
   - The question could refer to multiple different things
   - Pronouns are used without clear antecedents
4. For claim_types, only include types the question is specifically about:
   - "who does X report to" → ["reports_to"]
   - "where does X work" → ["works_at"]
   - "who works with X" → ["works_with"]
   - General questions → []
5. semantic_keywords: rephrase the question as a short search query.
   - "Who was Skilling's boss?" → "Jeff Skilling reports to supervisor manager"
   - "What concerns were raised about California?" → "California energy concerns problems"
   - Only include this if the question might benefit from semantic search.

Respond with ONLY the JSON object.
"""


# ------------------------------------------------------------------ #
# Main class
# ------------------------------------------------------------------ #

class QueryUnderstanding:
    """Parses natural language questions into structured QueryPlans."""

    def __init__(self, neo4j_driver, gemini_model: str = "gemini-3.1-flash-lite"):
        """
        Args:
            neo4j_driver: active Neo4j driver (for entity resolution)
            gemini_model: Gemini model name for question parsing
        """
        self.driver = neo4j_driver
        self.model_name = gemini_model

        # Initialize Gemini client (same pattern as Day 4 extractor)
        # self.client = genai.Client(
        #     vertexai=True,
        #     project=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        #     location="global",
        # )
        self.client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY", ""),
        )

        logger.info(
            "QueryUnderstanding initialized — model=%s", self.model_name
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def parse_query(self, question: str) -> QueryPlan:
        """
        Parse a natural language question into a QueryPlan.

        Steps:
          1. Call LLM to extract structured info from the question
          2. Resolve mentioned entity names to canonical graph IDs
          3. Detect ambiguity (multiple matches, zero matches)
          4. Choose retrieval strategy
          5. Return the complete QueryPlan

        Args:
            question: the user's raw natural language question

        Returns:
            QueryPlan with all fields populated
        """
        # Step 1: LLM parsing
        parsed = self._llm_parse(question)

        # Step 2: Entity resolution
        resolved_entities = self._resolve_entities(
            parsed.get("mentioned_entities", [])
        )

        # Step 3: Time constraint
        time_constraint = self._build_time_constraint(
            parsed.get("time_reference", {})
        )

        # Step 4: Ambiguity detection
        needs_clarification, clarification_reason = self._detect_ambiguity(
            parsed, resolved_entities
        )

        # Step 5: Choose retrieval strategy
        strategy = self._choose_strategy(
            resolved_entities, time_constraint, parsed
        )

        # Step 6: Question type
        question_type = self._parse_question_type(
            parsed.get("question_type", "what")
        )

        # Step 7: Claim types
        claim_types = parsed.get("claim_types", [])

        # Step 8: Semantic query
        semantic_query = parsed.get("semantic_keywords")

        plan = QueryPlan(
            raw_query=question,
            question_type=question_type,
            entities=resolved_entities,
            time_constraint=time_constraint,
            retrieval_strategy=strategy,
            claim_types=claim_types,
            needs_clarification=needs_clarification,
            clarification_reason=clarification_reason,
            semantic_query=semantic_query,
        )

        logger.info(
            "QueryPlan: type=%s, entities=%d, strategy=%s, clarify=%s",
            plan.question_type.value,
            len(plan.entities),
            plan.retrieval_strategy.value,
            plan.needs_clarification,
        )

        return plan

    # ------------------------------------------------------------------ #
    # Step 1: LLM parsing
    # ------------------------------------------------------------------ #

    def _llm_parse(self, question: str) -> dict:
        """
        Call Gemini to parse the question into structured JSON.

        Uses thinking_budget=0 (no reasoning tokens needed for parsing)
        and strict=False on json.loads (same pattern as Day 4 extractor).
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=question,
                config=GenerateContentConfig(
                    system_instruction=QUERY_PARSE_PROMPT,
                    temperature=0.0,  # deterministic parsing
                    thinking_config=ThinkingConfig(thinking_budget=0),
                ),
            )

            raw_text = response.text.strip()

            # Strip markdown fences if present
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)

            parsed = json.loads(raw_text, strict=False)
            logger.debug("LLM parse result: %s", parsed)
            return parsed

        except Exception as e:
            logger.error("LLM parsing failed: %s", e)
            # Return a safe fallback — treat as a concept query
            return {
                "mentioned_entities": [],
                "question_type": "what",
                "time_reference": {"type": "none"},
                "is_ambiguous": False,
                "claim_types": [],
                "semantic_keywords": question,
            }

    # ------------------------------------------------------------------ #
    # Step 2: Entity resolution
    # ------------------------------------------------------------------ #

    def _resolve_entities(
        self, mentioned: list[dict]
    ) -> list[ResolvedEntity]:
        """
        Resolve each mentioned entity name to a canonical graph ID
        using find_entity() from the temporal query engine.

        find_entity does partial name search across Person + Organization,
        including aliases, sorted by mention_count (most-referenced first).
        """
        resolved = []

        for entity_info in mentioned:
            raw_name = entity_info.get("name", "")
            entity_type_hint = entity_info.get("type", "unknown")

            if not raw_name.strip():
                continue

            # Call find_entity in Neo4j
            matches = self._find_entity_in_graph(raw_name)

            if not matches:
                # Entity not found — zero results
                resolved.append(ResolvedEntity(
                    raw_name=raw_name,
                    canonical_id=None,
                    canonical_name=None,
                    entity_type=entity_type_hint,
                    confidence=0.0,
                    alternatives=[],
                ))

            elif len(matches) == 1:
                # Exactly one match — high confidence
                match = matches[0]
                resolved.append(ResolvedEntity(
                    raw_name=raw_name,
                    canonical_id=match["id"],
                    canonical_name=match["name"],
                    entity_type=match.get("type", entity_type_hint),
                    confidence=1.0,
                    alternatives=[],
                ))

            else:
                # Multiple matches — take the top one but record alternatives
                top = matches[0]
                alts = matches[1:5]  # keep top 5 alternatives max

                # If the top match has significantly more mentions,
                # it's probably the right one
                top_mentions = top.get("mention_count", 0)
                second_mentions = matches[1].get("mention_count", 0) if len(matches) > 1 else 0

                if top_mentions > second_mentions * 3:
                    # Top match is dominant — use it confidently
                    confidence = 0.9
                else:
                    # Multiple plausible matches — ambiguous
                    confidence = 0.5

                resolved.append(ResolvedEntity(
                    raw_name=raw_name,
                    canonical_id=top["id"],
                    canonical_name=top["name"],
                    entity_type=top.get("type", entity_type_hint),
                    confidence=confidence,
                    alternatives=alts,
                ))

        return resolved

    def _find_entity_in_graph(self, name: str) -> list[dict]:
        """
        Search for an entity by name in Neo4j.

        Searches both Person and Organization nodes by canonical_name
        and aliases. Returns matches sorted by mention_count (highest first).

        Uses the same Cypher pattern as find_entity() from
        temporal_queries.py but returns raw dicts for our processing.
        """
        query = """
        MATCH (p:Person)
        WHERE p.is_deleted = false
          AND (
            toLower(p.canonical_name) CONTAINS toLower($name)
            OR any(alias IN p.aliases WHERE toLower(alias) CONTAINS toLower($name) AND NOT alias CONTAINS '@')
          )
        RETURN
            p.id AS id,
            p.canonical_name AS name,
            'person' AS type,
            p.mention_count AS mention_count,
            1 AS priority
        ORDER BY p.mention_count DESC
        LIMIT 10

        UNION

        MATCH (o:Organization)
        WHERE o.is_deleted = false
          AND toLower(o.canonical_name) CONTAINS toLower($name)
        RETURN
            o.id AS id,
            o.canonical_name AS name,
            'organization' AS type,
            o.mention_count AS mention_count,
            2 AS priority
        ORDER BY mention_count DESC
        LIMIT 10
        """

        with self.driver.session() as session:
            result = session.run(query, name=name)
            results = [dict(record) for record in result]
            results.sort(key=lambda r: (r.get("priority", 1), r.get("mention_count", 0)), reverse=True)
            return results

    # ------------------------------------------------------------------ #
    # Step 3: Time constraint building
    # ------------------------------------------------------------------ #

    def _build_time_constraint(self, time_ref: dict) -> TimeConstraint:
        """
        Convert the LLM's time_reference JSON into a TimeConstraint.
        """
        ref_type = time_ref.get("type", "none")

        if ref_type == "none" or not ref_type:
            return TimeConstraint(
                constraint_type=TimeConstraintType.NONE,
                raw_reference=None,
            )

        try:
            constraint_type = TimeConstraintType(ref_type)
        except ValueError:
            constraint_type = TimeConstraintType.NONE

        return TimeConstraint(
            constraint_type=constraint_type,
            date_from=time_ref.get("date_from"),
            date_to=time_ref.get("date_to"),
            raw_reference=time_ref.get("raw_text"),
        )

    # ------------------------------------------------------------------ #
    # Step 4: Ambiguity detection
    # ------------------------------------------------------------------ #

    def _detect_ambiguity(
        self, parsed: dict, resolved: list[ResolvedEntity]
    ) -> tuple[bool, Optional[str]]:
        """
        Determine whether the query needs clarification.

        Three sources of ambiguity:
        1. LLM flagged it as ambiguous
        2. Entity resolution found zero matches for a mentioned name
        3. Entity resolution found multiple plausible matches
        """
        # Source 1: LLM flagged ambiguity
        if parsed.get("is_ambiguous", False):
            return True, parsed.get("ambiguity_reason", "Query is ambiguous")

        for entity in resolved:
            # Source 2: Entity not found
            if entity.canonical_id is None:
                return True, f"Could not find '{entity.raw_name}' in the knowledge graph"

            # Source 3: Low-confidence resolution (multiple plausible matches)
            if entity.alternatives:
                alt_names = [a.get("name", "") for a in entity.alternatives[:3]]
                return True, (
                    f"'{entity.raw_name}' could refer to: "
                    f"{entity.canonical_name}, {', '.join(alt_names)}"
                )

        return False, None

    # ------------------------------------------------------------------ #
    # Step 5: Strategy selection
    # ------------------------------------------------------------------ #

    def _choose_strategy(
        self,
        entities: list[ResolvedEntity],
        time_constraint: TimeConstraint,
        parsed: dict,
    ) -> RetrievalStrategy:
        """
        Choose the retrieval strategy based on what was found.

        Decision logic:
        - Named entities resolved → GRAPH (structured traversal)
        - No entities + concept question → SEMANTIC (Qdrant)
        - Named entities + concept keywords → HYBRID (both)
        - Named entities not found → SEMANTIC (fallback to concept search)
        """
        has_resolved_entities = any(
            e.canonical_id is not None for e in entities
        )
        has_semantic_keywords = bool(parsed.get("semantic_keywords"))
        has_unresolved_entities = any(
            e.canonical_id is None for e in entities
        )

        if has_resolved_entities and has_semantic_keywords:
            # Both entity and concept — use hybrid
            return RetrievalStrategy.HYBRID

        if has_resolved_entities:
            # Entity-based question — graph is primary
            return RetrievalStrategy.GRAPH

        if has_semantic_keywords or has_unresolved_entities:
            # Concept-based or entity not in graph — semantic fallback
            return RetrievalStrategy.SEMANTIC

        # Default: try both
        return RetrievalStrategy.HYBRID

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _parse_question_type(self, type_str: str) -> QuestionType:
        """Safely parse question type from LLM output."""
        try:
            return QuestionType(type_str.lower())
        except ValueError:
            return QuestionType.WHAT  # safe default