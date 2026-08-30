"""
Chat route — the main interaction endpoint.

POST /api/chat takes a natural language question and runs the full
pipeline: follow-up resolution → query understanding → retrieval →
chatbot answer generation.

Day 34 additions:
  - session_id tracking for multi-turn conversations
  - Follow-up detection and rewriting before query understanding
  - Conversation history stored per session
"""

import logging

from fastapi import APIRouter, Depends

from src.api.dependencies import (
    CurrentUser,
    get_chatbot,
    get_conversation_memory,
    get_current_user,
    get_follow_up_resolver,
    get_query_understanding,
    get_retrieval_engine,
)
from src.api.models import (
    ChatRequest,
    ChatResponse,
    CitationItem,
    ClaimResult,
    ClarificationInfo,
    ClarificationOption,
    EntityProfile,
    RetrievalInfo,
)
from src.chatbot.chatbot import Chatbot
from src.chatbot.conversation import (
    ConversationMemory,
    FollowUpResolver,
    is_likely_follow_up,
)
from src.retrieval.query_understanding import QueryUnderstanding
from src.retrieval.retrieval_engine import RetrievalEngine

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
    query_understanding: QueryUnderstanding = Depends(get_query_understanding),
    retrieval_engine: RetrievalEngine = Depends(get_retrieval_engine),
    chatbot: Chatbot = Depends(get_chatbot),
    memory: ConversationMemory = Depends(get_conversation_memory),
    resolver: FollowUpResolver = Depends(get_follow_up_resolver),
):
    """
    Ask a natural language question about the Enron knowledge graph.

    Pipeline:
      0. Resolve session → create or retrieve conversation history
      1. Detect follow-up → rewrite into standalone question if needed
      2. Parse question → QueryPlan
      3. Execute QueryPlan → ContextPack
      4. Generate answer → cited natural language
      5. Store turn in conversation memory
      6. Format response as structured JSON

    Send session_id from a previous response to continue a conversation.
    Omit it (or send empty string) to start a new conversation.
    """
    logger.info(
        "Chat request from %s (clearance=%d): %s",
        user.username, user.clearance, request.question,
    )

    # ---- Step 0: Session management ----
    session_id = request.session_id or ""
    if not session_id or not memory.get_history(session_id):
        session_id = memory.create_session()
        logger.info("New session created: %s", session_id[:8])

    # ---- Step 1: Follow-up detection and rewriting ----
    original_question = request.question
    effective_question = request.question
    was_rewritten = False

    history = memory.get_history(session_id)
    if is_likely_follow_up(request.question, bool(history)):
        history_text = memory.format_history_for_prompt(session_id)
        recent_entities = memory.get_recent_entities(session_id)

        effective_question = resolver.resolve(
            question=request.question,
            history_text=history_text,
            recent_entities=recent_entities,
        )
        was_rewritten = (effective_question != request.question)
        if was_rewritten:
            logger.info(
                "Follow-up rewritten: '%s' → '%s'",
                request.question, effective_question,
            )

    # ---- Step 2: Parse the (possibly rewritten) question ----
    plan = query_understanding.parse_query(effective_question)

    # ---- Step 3: Execute retrieval with user's clearance ----
    pack = retrieval_engine.retrieve(plan, user_clearance=user.clearance)

    # ---- Step 4: Format context and generate answer ----
    context_text = retrieval_engine.format_context_for_llm(pack)

    chatbot_response = chatbot.generate_answer(
        question=effective_question,
        context_pack=pack,
        context_text=context_text,
    )

    # ---- Step 5: Store this turn in conversation memory ----
    entity_names = [
        e.canonical_name
        for e in plan.entities
        if e.canonical_name
    ]
    memory.add_turn(
        session_id=session_id,
        question=original_question,
        rewritten_question=effective_question if was_rewritten else None,
        answer=chatbot_response.answer,
        entities_mentioned=entity_names,
    )

    # ---- Step 6: Format structured response ----
    claims = [
        ClaimResult(
            claim_id=c.claim_id,
            claim_type=c.claim_type,
            subject_id=c.subject_id,
            subject_name=c.subject_name,
            object_id=c.object_id,
            object_name=c.object_name,
            confidence=c.confidence,
            valid_from=str(c.valid_from) if c.valid_from else None,
            valid_to=str(c.valid_to) if c.valid_to else None,
            status=c.status,
            mention_count=c.mention_count,
            relevance_score=round(c.relevance_score, 4),
            composite_score=round(c.composite_score, 4),
            source=c.source,
            evidence=c.evidence,
        )
        for c in pack.claims
    ]

    entities = [
        EntityProfile(
            id=e.get("id"),
            name=e.get("name"),
            type=e.get("type"),
            mention_count=e.get("mention_count"),
            aliases=e.get("aliases"),
            emails=e.get("emails"),
        )
        for e in pack.entities
    ]

    clarification = None
    if pack.clarification:
        clarification = ClarificationInfo(
            message=pack.clarification.message,
            options=[
                ClarificationOption(
                    id=opt.get("id", ""),
                    name=opt.get("name", ""),
                    type=opt.get("type", "unknown"),
                )
                for opt in pack.clarification.options
            ],
        )

    retrieval_info = RetrievalInfo(
        graph_results=pack.metadata.graph_results_count,
        semantic_results=pack.metadata.semantic_results_count,
        merged_count=pack.metadata.merged_count,
        total_results=pack.metadata.total_results,
        strategy=pack.metadata.strategy_used,
        time_ms=pack.metadata.retrieval_time_ms,
    )

    citations = [
        CitationItem(
            marker=c.marker,
            index=c.index,
            claim_id=c.claim_id,
            claim_type=c.claim_type,
            subject_name=c.subject_name,
            object_name=c.object_name,
            evidence_quote=c.evidence_quote,
            evidence_id=c.evidence_id,
            confidence=c.confidence,
        )
        for c in chatbot_response.citations
    ]

    return ChatResponse(
        question=original_question,
        effective_question=effective_question if was_rewritten else None,
        answer=chatbot_response.answer,
        citations=citations,
        claims=claims,
        entities=entities,
        clarification=clarification,
        retrieval_info=retrieval_info,
        context_text=context_text,
        session_id=session_id,
    )