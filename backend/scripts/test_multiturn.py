"""
Day 34 — Test multi-turn conversation with follow-up resolution.

Simulates a conversation where follow-up questions reference
previous turns using pronouns, temporal shifts, and topic pivots.

Run from backend/:
  python scripts/test_multiturn.py
"""

import logging
import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv

project_root = backend_dir.parent
load_dotenv(project_root / ".env")

from neo4j import GraphDatabase

from src.chatbot.chatbot import Chatbot
from src.chatbot.conversation import (
    ConversationMemory,
    FollowUpResolver,
    is_likely_follow_up,
)
from src.retrieval.qdrant_index import QdrantIndex
from src.retrieval.query_understanding import QueryUnderstanding
from src.retrieval.retrieval_engine import RetrievalEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    # ---- Connect to services ----
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    logger.info("Neo4j connected")

    qdrant = QdrantIndex(qdrant_url=qdrant_url)
    logger.info("QdrantIndex ready")

    qu = QueryUnderstanding(
        neo4j_driver=driver,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
    )
    logger.info("QueryUnderstanding ready")

    engine = RetrievalEngine(neo4j_driver=driver, qdrant_index=qdrant)
    logger.info("RetrievalEngine ready")

    chatbot = Chatbot(
        gemini_model=os.getenv("GEMINI_CHAT_MODEL", "gemini-3.6-flash"),
    )
    logger.info("Chatbot ready")

    memory = ConversationMemory(max_turns=5)
    resolver = FollowUpResolver(
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
    )
    logger.info("ConversationMemory and FollowUpResolver ready")

    # ---- Multi-turn conversation ----
    # This simulates a real user conversation with follow-ups
    conversation = [
        "Who does Sally Beck report to?",            # standalone
        "What about in March 2001?",                 # temporal follow-up
        "Who reports to her?",                       # pronoun + topic change
        "Tell me about Steven Kean",                 # new topic (not a follow-up)
        "What is his relationship with Jeff Dasovich?",  # pronoun follow-up
    ]

    session_id = memory.create_session()
    print(f"\nSession: {session_id[:8]}...")
    print(f"{'='*70}")

    for i, question in enumerate(conversation, 1):
        print(f"\n{'='*70}")
        print(f"  Turn {i}: \"{question}\"")
        print(f"{'='*70}")

        # Step 1: Follow-up detection
        history = memory.get_history(session_id)
        is_followup = is_likely_follow_up(question, bool(history))
        print(f"  Follow-up detected: {is_followup}")

        # Step 2: Rewrite if follow-up
        effective_question = question
        if is_followup:
            history_text = memory.format_history_for_prompt(session_id)
            recent_entities = memory.get_recent_entities(session_id)
            effective_question = resolver.resolve(
                question=question,
                history_text=history_text,
                recent_entities=recent_entities,
            )
            if effective_question != question:
                print(f"  Rewritten to: \"{effective_question}\"")

        # Step 3: Parse + retrieve + generate
        plan = qu.parse_query(effective_question)
        pack = engine.retrieve(plan, user_clearance=4)
        context_text = engine.format_context_for_llm(pack)

        result = chatbot.generate_answer(
            question=effective_question,
            context_pack=pack,
            context_text=context_text,
        )

        # Step 4: Store turn
        entity_names = [
            e.canonical_name for e in plan.entities if e.canonical_name
        ]
        memory.add_turn(
            session_id=session_id,
            question=question,
            rewritten_question=effective_question if is_followup else None,
            answer=result.answer,
            entities_mentioned=entity_names,
        )

        # Step 5: Display
        print(f"\n  Strategy: {pack.metadata.strategy_used}")
        print(f"  Claims: {len(pack.claims)} | Citations: {len(result.citations)}")
        print(f"  Entities in memory: {memory.get_recent_entities(session_id)}")

        print(f"\n  ANSWER:")
        print(f"  {'-'*60}")
        words = result.answer.split()
        line = "  "
        for word in words:
            if len(line) + len(word) + 1 > 72:
                print(line)
                line = "  " + word
            else:
                line += " " + word if line.strip() else "  " + word
        if line.strip():
            print(line)
        print(f"  {'-'*60}")

    # ---- Summary ----
    print(f"\n{'='*70}")
    print(f"  Conversation complete — {len(conversation)} turns")
    print(f"  Session history: {len(memory.get_history(session_id))} turns stored")
    print(f"  Entities discussed: {memory.get_recent_entities(session_id)}")
    print(f"{'='*70}")

    driver.close()


if __name__ == "__main__":
    main()