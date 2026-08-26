"""
Retrieval engine — executes QueryPlans by combining graph traversal
and semantic search, then merging and ranking results.

This is the orchestrator that connects:
  - Day 24: temporal_queries.py (graph-side retrieval)
  - Day 29: qdrant_index.py (vector-side retrieval)
  - Day 30: query_understanding.py (produces QueryPlans)

The output is a ContextPack — everything the chatbot (Day 33)
needs to generate a grounded, cited answer.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.retrieval.query_understanding import (
    QueryPlan,
    QuestionType,
    ResolvedEntity,
    RetrievalStrategy,
    TimeConstraintType,
)
from src.retrieval.qdrant_index import QdrantIndex

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Output data classes
# ------------------------------------------------------------------ #

@dataclass
class RetrievedClaim:
    """A claim retrieved from either graph or semantic search."""
    claim_id: str
    claim_type: str
    subject_id: str
    subject_name: str
    object_id: str
    object_name: str
    confidence: float
    valid_from: Optional[str]
    valid_to: Optional[str]
    status: str
    mention_count: int
    evidence: list[dict] = field(default_factory=list)
    # Scoring fields
    relevance_score: float = 0.0    # from semantic search (0-1)
    recency_boost: float = 1.0     # time-based boost
    composite_score: float = 0.0   # final ranking score
    source: str = ""               # "graph", "semantic", or "both"


@dataclass
class RetrievalMetadata:
    """Statistics about the retrieval process."""
    graph_results_count: int = 0
    semantic_results_count: int = 0
    merged_count: int = 0
    total_results: int = 0
    strategy_used: str = ""
    retrieval_time_ms: float = 0.0


@dataclass
class ClarificationResponse:
    """Returned instead of results when the query needs clarification."""
    message: str
    options: list[dict] = field(default_factory=list)


@dataclass
class ContextPack:
    """Everything the chatbot needs to generate an answer.

    Contains ranked claims with evidence, entity profiles,
    and metadata about the retrieval process.
    """
    claims: list[RetrievedClaim]
    entities: list[dict]
    query_plan: QueryPlan
    metadata: RetrievalMetadata
    clarification: Optional[ClarificationResponse] = None


# ------------------------------------------------------------------ #
# Retrieval Engine
# ------------------------------------------------------------------ #

class RetrievalEngine:
    """Executes QueryPlans using graph traversal and semantic search."""

    def __init__(
        self,
        neo4j_driver,
        qdrant_index: QdrantIndex,
        default_top_k: int = 15,
    ):
        """
        Args:
            neo4j_driver: active Neo4j driver
            qdrant_index: initialized QdrantIndex from Day 29
            default_top_k: max results to return in context pack
        """
        self.driver = neo4j_driver
        self.qdrant = qdrant_index
        self.default_top_k = default_top_k

        # Import temporal queries here to avoid circular imports
        # These methods are called directly via Neo4j session
        logger.info("RetrievalEngine initialized — top_k=%d", default_top_k)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def retrieve(
        self,
        plan: QueryPlan,
        user_clearance: int = 4,
        top_k: Optional[int] = None,
    ) -> ContextPack:
        """
        Execute a QueryPlan and return a ContextPack.

        Args:
            plan: structured query plan from Day 30
            user_clearance: user's access level (1-4)
            top_k: override for max results

        Returns:
            ContextPack with ranked claims, evidence, and entities
        """
        import time
        start = time.time()

        top_k = top_k or self.default_top_k

        # Step 1: Handle clarification
        if plan.needs_clarification and not any(
            e.canonical_id for e in plan.entities
        ):
            # No resolved entities — but if we have semantic keywords,
            # still try semantic search before giving up
            if plan.semantic_query or plan.raw_query:
                # Override strategy to semantic-only
                plan.retrieval_strategy = RetrievalStrategy.SEMANTIC
            else:
                return self._build_clarification_pack(plan)

        # Step 2: Run retrieval based on strategy
        graph_results = []
        semantic_results = []

        if plan.retrieval_strategy in (
            RetrievalStrategy.GRAPH, RetrievalStrategy.HYBRID
        ):
            graph_results = self._graph_retrieve(plan, user_clearance)
            logger.info("Graph retrieval: %d results", len(graph_results))

        if plan.retrieval_strategy in (
            RetrievalStrategy.SEMANTIC, RetrievalStrategy.HYBRID
        ):
            semantic_results = self._semantic_retrieve(
                plan, user_clearance, top_k
            )
            logger.info("Semantic retrieval: %d results", len(semantic_results))

        # Step 3: Merge and deduplicate
        merged = self._merge_results(graph_results, semantic_results)

        # Step 4: Rank by composite score
        ranked = self._rank_results(merged)

        # Step 5: Trim to top_k
        ranked = ranked[:top_k]

        # Step 6: Fetch evidence for graph results that don't have it
        self._enrich_with_evidence(ranked)

        # Step 7: Fetch entity profiles
        entities = self._fetch_entity_profiles(plan)

        elapsed = (time.time() - start) * 1000

        metadata = RetrievalMetadata(
            graph_results_count=len(graph_results),
            semantic_results_count=len(semantic_results),
            merged_count=len(graph_results) + len(semantic_results) - len(merged),
            total_results=len(ranked),
            strategy_used=plan.retrieval_strategy.value,
            retrieval_time_ms=round(elapsed, 1),
        )

        logger.info(
            "Retrieval complete: %d results in %.1fms "
            "(graph=%d, semantic=%d, merged=%d)",
            len(ranked), elapsed,
            len(graph_results), len(semantic_results),
            metadata.merged_count,
        )

        pack = ContextPack(
            claims=ranked,
            entities=entities,
            query_plan=plan,
            metadata=metadata,
        )

        # Attach clarification if needed (but we still have results)
        if plan.needs_clarification:
            pack.clarification = ClarificationResponse(
                message=plan.clarification_reason or "Multiple interpretations possible",
                options=self._build_clarification_options(plan),
            )

        return pack

    # ------------------------------------------------------------------ #
    # Step 1: Clarification
    # ------------------------------------------------------------------ #

    def _build_clarification_pack(self, plan: QueryPlan) -> ContextPack:
        """Build a ContextPack that only contains a clarification request."""
        options = self._build_clarification_options(plan)

        return ContextPack(
            claims=[],
            entities=[],
            query_plan=plan,
            metadata=RetrievalMetadata(strategy_used="clarification"),
            clarification=ClarificationResponse(
                message=plan.clarification_reason or "Could you clarify your question?",
                options=options,
            ),
        )

    def _build_clarification_options(self, plan: QueryPlan) -> list[dict]:
        """Extract clarification options from ambiguous entities."""
        options = []
        for entity in plan.entities:
            # Add the primary match
            if entity.canonical_id:
                options.append({
                    "id": entity.canonical_id,
                    "name": entity.canonical_name,
                    "type": entity.entity_type,
                })
            # Add alternatives
            for alt in entity.alternatives:
                alt_id = alt.get("id")
                alt_name = alt.get("name", "")
                if alt_id and alt_name:
                    options.append({
                        "id": alt_id,
                        "name": alt_name,
                        "type": alt.get("type", "unknown"),
                    })
        return options

    # ------------------------------------------------------------------ #
    # Step 2a: Graph retrieval
    # ------------------------------------------------------------------ #

    def _graph_retrieve(
        self, plan: QueryPlan, user_clearance: int
    ) -> list[RetrievedClaim]:
        """
        Retrieve claims from Neo4j based on the query plan.

        Chooses the temporal query method based on question_type
        and time_constraint, then converts raw graph results
        to RetrievedClaim objects.
        """
        results = []

        for entity in plan.entities:
            if not entity.canonical_id:
                continue

            entity_id = entity.canonical_id
            claims_data = []

            # Choose temporal method based on question type + time constraint
            if plan.question_type == QuestionType.HISTORY:
                claims_data = self._query_full_history(
                    entity_id, user_clearance
                )

            elif plan.time_constraint.constraint_type == TimeConstraintType.POINT:
                date = plan.time_constraint.date_from
                if date:
                    claims_data = self._query_state_at(
                        entity_id, date, user_clearance
                    )

            elif plan.time_constraint.constraint_type == TimeConstraintType.RANGE:
                # For ranges, query state at the midpoint
                # (or use date_from as the starting point)
                date = plan.time_constraint.date_from
                if date:
                    claims_data = self._query_state_at(
                        entity_id, date, user_clearance
                    )

            elif plan.time_constraint.constraint_type in (
                TimeConstraintType.BEFORE, TimeConstraintType.AFTER
            ):
                date = (
                    plan.time_constraint.date_to
                    if plan.time_constraint.constraint_type == TimeConstraintType.BEFORE
                    else plan.time_constraint.date_from
                )
                if date:
                    claims_data = self._query_state_at(
                        entity_id, date, user_clearance
                    )

            elif plan.question_type in (
                QuestionType.CURRENT, QuestionType.WHO,
                QuestionType.WHAT, QuestionType.YES_NO,
            ):
                claims_data = self._query_current_state(
                    entity_id, user_clearance
                )

            else:
                # Default: get all current relationships
                claims_data = self._query_current_state(
                    entity_id, user_clearance
                )

            # Filter by claim_type if the plan specifies
            if plan.claim_types and claims_data:
                claims_data = [
                    c for c in claims_data
                    if c.get("claim_type") in plan.claim_types
                ]

            # Convert to RetrievedClaim objects
            for claim in claims_data:
                results.append(RetrievedClaim(
                    claim_id=claim.get("claim_id", ""),
                    claim_type=claim.get("claim_type", ""),
                    subject_id=claim.get("subject_id", ""),
                    subject_name=claim.get("subject_name", ""),
                    object_id=claim.get("object_id", ""),
                    object_name=claim.get("object_name", ""),
                    confidence=claim.get("confidence", 0.0),
                    valid_from=_format_date(claim.get("valid_from")),
                    valid_to=_format_date(claim.get("valid_to")),
                    status=claim.get("status", ""),
                    mention_count=claim.get("mention_count", 0),
                    relevance_score=1.0,  # graph results are exact matches
                    source="graph",
                ))

        return results

    def _query_current_state(
        self, entity_id: str, clearance: int
    ) -> list[dict]:
        """Get current claims where entity is subject or object."""
        query = """
        MATCH (c:Claim)
        WHERE (c.subject_id = $entity_id OR c.object_id = $entity_id)
          AND c.is_deleted = false
          AND c.status = 'current'
          AND c.access_level <= $clearance
        RETURN
            c.id AS claim_id,
            c.claim_type AS claim_type,
            c.subject_id AS subject_id,
            c.subject_name AS subject_name,
            c.object_id AS object_id,
            c.object_name AS object_name,
            c.confidence AS confidence,
            c.valid_from AS valid_from,
            c.valid_to AS valid_to,
            c.status AS status,
            c.mention_count AS mention_count,
            c.access_level AS access_level
        ORDER BY c.confidence DESC
        """
        with self.driver.session() as session:
            result = session.run(
                query, entity_id=entity_id, clearance=clearance
            )
            return [dict(r) for r in result]

    def _query_state_at(
        self, entity_id: str, date: str, clearance: int
    ) -> list[dict]:
        """Get claims valid at a specific date."""
        query = """
        MATCH (c:Claim)
        WHERE (c.subject_id = $entity_id OR c.object_id = $entity_id)
          AND c.is_deleted = false
          AND c.valid_from IS NOT NULL
          AND c.valid_from <= $date
          AND (c.valid_to IS NULL OR c.valid_to > $date)
          AND c.access_level <= $clearance
        RETURN
            c.id AS claim_id,
            c.claim_type AS claim_type,
            c.subject_id AS subject_id,
            c.subject_name AS subject_name,
            c.object_id AS object_id,
            c.object_name AS object_name,
            c.confidence AS confidence,
            c.valid_from AS valid_from,
            c.valid_to AS valid_to,
            c.status AS status,
            c.mention_count AS mention_count,
            c.access_level AS access_level
        ORDER BY c.valid_from DESC
        """
        with self.driver.session() as session:
            result = session.run(
                query, entity_id=entity_id, date=date, clearance=clearance
            )
            return [dict(r) for r in result]

    def _query_full_history(
        self, entity_id: str, clearance: int
    ) -> list[dict]:
        """Get all claims (current + superseded) for an entity."""
        query = """
        MATCH (c:Claim)
        WHERE (c.subject_id = $entity_id OR c.object_id = $entity_id)
          AND c.is_deleted = false
          AND c.access_level <= $clearance
        RETURN
            c.id AS claim_id,
            c.claim_type AS claim_type,
            c.subject_id AS subject_id,
            c.subject_name AS subject_name,
            c.object_id AS object_id,
            c.object_name AS object_name,
            c.confidence AS confidence,
            c.valid_from AS valid_from,
            c.valid_to AS valid_to,
            c.status AS status,
            c.mention_count AS mention_count,
            c.access_level AS access_level
        ORDER BY c.valid_from ASC
        """
        with self.driver.session() as session:
            result = session.run(
                query, entity_id=entity_id, clearance=clearance
            )
            return [dict(r) for r in result]

    # ------------------------------------------------------------------ #
    # Step 2b: Semantic retrieval
    # ------------------------------------------------------------------ #

    def _semantic_retrieve(
        self, plan: QueryPlan, user_clearance: int, top_k: int
    ) -> list[RetrievedClaim]:
        """
        Retrieve evidence from Qdrant via semantic search,
        then convert to RetrievedClaim format.
        """
        search_query = plan.semantic_query or plan.raw_query

        # Build filters from the plan
        entity_id = None
        if plan.entities and plan.entities[0].canonical_id:
            entity_id = plan.entities[0].canonical_id

        claim_type = None
        if plan.claim_types and len(plan.claim_types) == 1:
            claim_type = plan.claim_types[0]

        date_from = plan.time_constraint.date_from
        date_to = plan.time_constraint.date_to

        # Run semantic search
        hits = self.qdrant.semantic_search(
            query=search_query,
            top_k=top_k,
            max_access_level=user_clearance,
            claim_type=claim_type,
            date_from=date_from,
            date_to=date_to,
            entity_id=entity_id,
        )

        # Convert hits to RetrievedClaim objects
        # Group by claim_id since multiple evidence items
        # may belong to the same claim
        claims_by_id = {}
        for hit in hits:
            cid = hit.get("claim_id", "")
            if not cid:
                continue

            if cid not in claims_by_id:
                claims_by_id[cid] = RetrievedClaim(
                    claim_id=cid,
                    claim_type=hit.get("claim_type", ""),
                    subject_id=hit.get("subject_id", ""),
                    subject_name=hit.get("subject_name", ""),  # (not->now) in Qdrant payload
                    object_id=hit.get("object_id", ""),
                    object_name=hit.get("object_name", ""),   # (not->now) in Qdrant payload
                    confidence=hit.get("confidence", 0.0),
                    valid_from=hit.get("valid_from"),
                    valid_to=hit.get("valid_to"),    # (not->now) in Qdrant payload
                    status=hit.get("status", ""),        # (not->now) in Qdrant payload
                    mention_count=hit.get("mention_count", 0),  # (not->now) in Qdrant payload
                    relevance_score=hit.get("score", 0.0),
                    source="semantic",
                    evidence=[{
                        "evidence_id": hit.get("evidence_id"),
                        "quote": hit.get("quote"),
                        "message_id": hit.get("message_id"),
                        "score": hit.get("score", 0.0),
                    }],
                )
            else:
                # Same claim, additional evidence
                claims_by_id[cid].evidence.append({
                    "evidence_id": hit.get("evidence_id"),
                    "quote": hit.get("quote"),
                    "message_id": hit.get("message_id"),
                    "score": hit.get("score", 0.0),
                })
                # Update relevance to max evidence score
                claims_by_id[cid].relevance_score = max(
                    claims_by_id[cid].relevance_score,
                    hit.get("score", 0.0),
                )

        return list(claims_by_id.values())

    # ------------------------------------------------------------------ #
    # Step 3: Merge and deduplicate
    # ------------------------------------------------------------------ #

    def _merge_results(
        self,
        graph_results: list[RetrievedClaim],
        semantic_results: list[RetrievedClaim],
    ) -> list[RetrievedClaim]:
        """
        Merge graph and semantic results, deduplicating by claim_id.

        If the same claim appears in both:
        - Keep the graph version (has richer metadata)
        - Copy the relevance_score from semantic (has similarity score)
        - Mark source as "both"
        - Give a score boost for appearing in both paths
        """
        merged = {}

        # Add graph results first (richer metadata)
        for claim in graph_results:
            merged[claim.claim_id] = claim

        # Merge semantic results
        for claim in semantic_results:
            if claim.claim_id in merged:
                # Duplicate — enrich the graph version
                existing = merged[claim.claim_id]
                existing.relevance_score = max(
                    existing.relevance_score, claim.relevance_score
                )
                existing.source = "both"
                # Merge evidence lists
                existing_evidence_ids = {
                    e.get("evidence_id") for e in existing.evidence
                }
                for ev in claim.evidence:
                    if ev.get("evidence_id") not in existing_evidence_ids:
                        existing.evidence.append(ev)
            else:
                merged[claim.claim_id] = claim

        return list(merged.values())

    # ------------------------------------------------------------------ #
    # Step 4: Ranking
    # ------------------------------------------------------------------ #

    def _rank_results(
        self, claims: list[RetrievedClaim]
    ) -> list[RetrievedClaim]:
        """
        Compute composite score and sort claims.

        composite_score = relevance × recency_boost × confidence × source_boost

        - relevance_score: 1.0 for graph (exact match), 0-1 for semantic
        - recency_boost: newer claims score higher (within the Enron timeframe)
        - confidence: from extraction pipeline (0-1)
        - source_boost: 1.2 if found by both paths (cross-validated)
        """
        reference_date = datetime(2002, 1, 1)

        for claim in claims:
            # Recency boost: claims from late 2001 score higher than 1997
            recency = 1.0
            if claim.valid_from:
                try:
                    claim_date = datetime.fromisoformat(str(claim.valid_from))
                    years_old = (reference_date - claim_date).days / 365
                    # Newer = higher boost, range roughly 0.7 to 1.3
                    recency = max(0.7, 1.3 - (years_old * 0.1))
                except (ValueError, TypeError):
                    recency = 1.0
            claim.recency_boost = recency

            # Source boost: found by both paths = cross-validated
            source_boost = 1.2 if claim.source == "both" else 1.0

            # Composite score
            claim.composite_score = (
                claim.relevance_score
                * claim.recency_boost
                * claim.confidence
                * source_boost
            )

        # Sort by composite score descending
        claims.sort(key=lambda c: c.composite_score, reverse=True)
        return claims

    # ------------------------------------------------------------------ #
    # Step 5: Evidence enrichment
    # ------------------------------------------------------------------ #

    def _enrich_with_evidence(self, claims: list[RetrievedClaim]):
        """
        Fetch evidence from Neo4j for claims that don't have it yet.
        Graph results arrive without evidence; semantic results already have it.
        """
        for claim in claims:
            if claim.evidence:
                continue  # already has evidence from semantic search

            if not claim.claim_id:
                continue

            query = """
            MATCH (c:Claim {id: $claim_id})-[:SUPPORTED_BY]->(e:Evidence)
            WHERE e.is_deleted = false
            OPTIONAL MATCH (e)-[:FROM_MESSAGE]->(m:Message)
            RETURN
                e.evidence_id AS evidence_id,
                e.quote AS quote,
                e.char_start AS char_start,
                e.char_end AS char_end,
                e.evidence_verified AS evidence_verified,
                m.message_id AS message_id,
                m.subject AS email_subject,
                m.from_addr AS from_addr,
                m.date AS email_date
            ORDER BY e.confidence DESC
            LIMIT 5
            """
            with self.driver.session() as session:
                result = session.run(query, claim_id=claim.claim_id)
                claim.evidence = [dict(r) for r in result]

    # ------------------------------------------------------------------ #
    # Step 6: Entity profiles
    # ------------------------------------------------------------------ #

    def _fetch_entity_profiles(self, plan: QueryPlan) -> list[dict]:
        """Fetch entity profiles for all resolved entities in the plan."""
        profiles = []

        for entity in plan.entities:
            if not entity.canonical_id:
                continue

            query = """
            MATCH (n)
            WHERE n.id = $entity_id AND n.is_deleted = false
            RETURN
                n.id AS id,
                n.canonical_name AS name,
                labels(n)[0] AS type,
                n.mention_count AS mention_count,
                n.aliases AS aliases,
                n.emails AS emails
            """
            with self.driver.session() as session:
                result = session.run(query, entity_id=entity.canonical_id)
                record = result.single()
                if record:
                    profiles.append(dict(record))

        return profiles

    # ------------------------------------------------------------------ #
    # Formatting helpers
    # ------------------------------------------------------------------ #

    def format_context_for_llm(self, pack: ContextPack) -> str:
        """
        Format a ContextPack into a text block for the LLM prompt.

        This is what gets injected into the chatbot's system prompt
        as the "context" for generating an answer.
        """
        if pack.clarification and not pack.claims:
            return f"CLARIFICATION NEEDED: {pack.clarification.message}"

        parts = []

        # Entity profiles
        if pack.entities:
            parts.append("=== ENTITIES ===")
            for e in pack.entities:
                aliases = e.get("aliases", [])
                alias_str = f" (also known as: {', '.join(aliases[:3])})" if aliases else ""
                parts.append(
                    f"- {e.get('name', '?')} [{e.get('type', '?')}]"
                    f"{alias_str}, {e.get('mention_count', 0)} mentions"
                )

        # Claims with evidence
        if pack.claims:
            parts.append("\n=== CLAIMS (ranked by relevance) ===")
            for i, claim in enumerate(pack.claims, 1):
                parts.append(
                    f"\n[Claim {i}] {claim.subject_name} "
                    f"{claim.claim_type} {claim.object_name}"
                )
                parts.append(
                    f"  Confidence: {claim.confidence:.2f} | "
                    f"Valid: {claim.valid_from or '?'} to "
                    f"{claim.valid_to or 'present'} | "
                    f"Status: {claim.status or 'current'}"
                )

                # Evidence
                for j, ev in enumerate(claim.evidence[:3], 1):
                    quote = ev.get("quote", "")
                    msg_id = ev.get("message_id", "")
                    parts.append(
                        f"  Evidence {i}.{j} [{msg_id}]: \"{quote}\""
                    )

        # Metadata
        parts.append(f"\n=== RETRIEVAL INFO ===")
        parts.append(
            f"Strategy: {pack.metadata.strategy_used} | "
            f"Results: {pack.metadata.total_results} | "
            f"Time: {pack.metadata.retrieval_time_ms:.0f}ms"
        )

        if pack.clarification:
            parts.append(
                f"NOTE: Query may be ambiguous — "
                f"{pack.clarification.message}"
            )

        return "\n".join(parts)


# ------------------------------------------------------------------ #
# Module-level helpers
# ------------------------------------------------------------------ #

def _format_date(date_val) -> Optional[str]:
    """Convert Neo4j date objects to ISO strings safely."""
    if date_val is None:
        return None
    if hasattr(date_val, "iso_format"):
        return date_val.iso_format()
    return str(date_val)