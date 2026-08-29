# """
# Chat route — the main interaction endpoint.

# POST /api/chat takes a natural language question and runs the full
# pipeline: query understanding → retrieval → context assembly.

# Day 33 will add LLM answer generation on top of this.
# For now, the response returns the raw ContextPack as structured JSON.
# """

# import logging

# from fastapi import APIRouter, Depends

# from src.api.dependencies import (
#     CurrentUser,
#     get_current_user,
#     get_query_understanding,
#     get_retrieval_engine,
# )
# from src.api.models import (
#     ChatRequest,
#     ChatResponse,
#     ClaimResult,
#     ClarificationInfo,
#     ClarificationOption,
#     EntityProfile,
#     RetrievalInfo,
# )
# from src.retrieval.query_understanding import QueryUnderstanding
# from src.retrieval.retrieval_engine import RetrievalEngine

# logger = logging.getLogger(__name__)

# router = APIRouter()


# @router.post("/chat", response_model=ChatResponse)
# async def chat(
#     request: ChatRequest,
#     user: CurrentUser = Depends(get_current_user),
#     query_understanding: QueryUnderstanding = Depends(get_query_understanding),
#     retrieval_engine: RetrievalEngine = Depends(get_retrieval_engine),
# ):
#     """
#     Ask a natural language question about the Enron knowledge graph.

#     Pipeline:
#       1. Parse question → QueryPlan (entity extraction, time, strategy)
#       2. Execute QueryPlan → ContextPack (graph + semantic retrieval)
#       3. Format response as structured JSON

#     The user's clearance level (from auth) filters results —
#     they only see claims at or below their access level.
#     """
#     logger.info(
#         "Chat request from %s (clearance=%d): %s",
#         user.username, user.clearance, request.question,
#     )

#     # Step 1: Parse the question
#     plan = query_understanding.parse_query(request.question)

#     # Step 2: Execute retrieval with user's clearance
#     pack = retrieval_engine.retrieve(plan, user_clearance=user.clearance)

#     # Step 3: Format response
#     claims = [
#         ClaimResult(
#             claim_id=c.claim_id,
#             claim_type=c.claim_type,
#             subject_id=c.subject_id,
#             subject_name=c.subject_name,
#             object_id=c.object_id,
#             object_name=c.object_name,
#             confidence=c.confidence,
#             valid_from=str(c.valid_from) if c.valid_from else None,
#             valid_to=str(c.valid_to) if c.valid_to else None,
#             status=c.status,
#             mention_count=c.mention_count,
#             relevance_score=round(c.relevance_score, 4),
#             composite_score=round(c.composite_score, 4),
#             source=c.source,
#             evidence=c.evidence,
#         )
#         for c in pack.claims
#     ]

#     entities = [
#         EntityProfile(
#             id=e.get("id"),
#             name=e.get("name"),
#             type=e.get("type"),
#             mention_count=e.get("mention_count"),
#             aliases=e.get("aliases"),
#             emails=e.get("emails"),
#         )
#         for e in pack.entities
#     ]

#     clarification = None
#     if pack.clarification:
#         clarification = ClarificationInfo(
#             message=pack.clarification.message,
#             options=[
#                 ClarificationOption(
#                     id=opt.get("id", ""),
#                     name=opt.get("name", ""),
#                     type=opt.get("type", "unknown"),
#                 )
#                 for opt in pack.clarification.options
#             ],
#         )

#     retrieval_info = RetrievalInfo(
#         graph_results=pack.metadata.graph_results_count,
#         semantic_results=pack.metadata.semantic_results_count,
#         merged_count=pack.metadata.merged_count,
#         total_results=pack.metadata.total_results,
#         strategy=pack.metadata.strategy_used,
#         time_ms=pack.metadata.retrieval_time_ms,
#     )

#     # Format context text for Day 33 chatbot
#     context_text = retrieval_engine.format_context_for_llm(pack)

#     return ChatResponse(
#         question=request.question,
#         claims=claims,
#         entities=entities,
#         clarification=clarification,
#         retrieval_info=retrieval_info,
#         context_text=context_text,
#     )


"""
Chat route — the main interaction endpoint.

POST /api/chat takes a natural language question and runs the full
pipeline: query understanding → retrieval → chatbot answer generation.

Returns both the raw ContextPack data (claims, entities) AND the
generated natural language answer with resolved citations.
"""

import logging

from fastapi import APIRouter, Depends

from src.api.dependencies import (
    CurrentUser,
    get_chatbot,
    get_current_user,
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
):
    """
    Ask a natural language question about the Enron knowledge graph.

    Pipeline:
      1. Parse question → QueryPlan (entity extraction, time, strategy)
      2. Execute QueryPlan → ContextPack (graph + semantic retrieval)
      3. Generate answer → cited natural language (Gemini)
      4. Format response as structured JSON

    The user's clearance level (from auth) filters results —
    they only see claims at or below their access level.
    """
    logger.info(
        "Chat request from %s (clearance=%d): %s",
        user.username, user.clearance, request.question,
    )

    # Step 1: Parse the question
    plan = query_understanding.parse_query(request.question)

    # Step 2: Execute retrieval with user's clearance
    pack = retrieval_engine.retrieve(plan, user_clearance=user.clearance)

    # Step 3: Format context text for LLM
    context_text = retrieval_engine.format_context_for_llm(pack)

    # Step 4: Generate answer with citations
    chatbot_response = chatbot.generate_answer(
        question=request.question,
        context_pack=pack,
        context_text=context_text,
    )

    # Step 5: Format structured response
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

    # Step 6: Format citations from chatbot response
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
        question=request.question,
        answer=chatbot_response.answer,
        citations=citations,
        claims=claims,
        entities=entities,
        clarification=clarification,
        retrieval_info=retrieval_info,
        context_text=context_text,
    )