"""
Day 33 — Test the RAG chatbot end-to-end.

Runs the same 6 test questions from Day 31, but now goes through
the full pipeline including answer generation:
  question → QueryUnderstanding → RetrievalEngine → Chatbot → answer

Run from backend/:
  python scripts/test_chatbot.py
"""

import logging
import os
import sys
from pathlib import Path

# Add backend/src to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv

# Load .env from project root
project_root = backend_dir.parent
load_dotenv(project_root / ".env")

from neo4j import GraphDatabase

from src.chatbot.chatbot import Chatbot
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
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    )
    logger.info("QueryUnderstanding ready")

    engine = RetrievalEngine(neo4j_driver=driver, qdrant_index=qdrant)
    logger.info("RetrievalEngine ready")

    chatbot = Chatbot(
        gemini_model=os.getenv("GEMINI_CHAT_MODEL", "gemini-3.6-flash"),
    )
    logger.info("Chatbot ready")

    # ---- Test questions ----
    questions = [
        "Who does Sally Beck report to?",
        "Who did Sally Beck report to in March 2001?",
        "Show me the complete reporting history for Sally Beck",
        "What concerns were raised about California energy prices?",
        "What is the relationship between Steven Kean and Jeff Dasovich?",
        "What decisions were made about the Mahonia deal?",
    ]

    for i, question in enumerate(questions, start=1):
        print(f"\n{'='*70}")
        print(f"  Q{i}: {question}")
        print(f"{'='*70}")

        # Step 1: Parse
        plan = qu.parse_query(question)

        # Step 2: Retrieve (clearance 4 = executive, sees everything)
        pack = engine.retrieve(plan, user_clearance=4)

        # ------for debugging purpose only------
        # if question == "Who does Sally Beck report to?":
        #     print("\n  DEBUG — Q1 claims (checking for blank names):")
        #     for j, claim in enumerate(pack.claims, 1):
        #         print(
        #             f"    {j}. source={claim.source} claim_id={claim.claim_id} "
        #             f"subj='{claim.subject_name}' obj='{claim.object_name}'"
        #         )


        # Step 3: Format context
        context_text = engine.format_context_for_llm(pack)

        # Step 4: Generate answer
        result = chatbot.generate_answer(
            question=question,
            context_pack=pack,
            context_text=context_text,
        )

        # ---- Display results ----
        print(f"\n  Strategy: {pack.metadata.strategy_used}")
        print(f"  Claims found: {len(pack.claims)}")
        print(f"  Citations in answer: {len(result.citations)}")
        if result.has_clarification:
            print(f"  ⚠ Clarification needed")
        print(f"\n  ANSWER:")
        print(f"  {'-'*60}")

        # Word-wrap the answer for readability
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

        if result.citations:
            print(f"\n  CITATIONS:")
            for cit in result.citations:
                quote_preview = cit.evidence_quote[:60] + "..." \
                    if len(cit.evidence_quote) > 60 else cit.evidence_quote
                print(
                    f"    {cit.marker} {cit.subject_name} "
                    f"{cit.claim_type} {cit.object_name} "
                    f"(conf={cit.confidence:.2f})"
                )
                if quote_preview:
                    print(f"        \"{quote_preview}\"")

    # ---- Cleanup ----
    driver.close()
    print(f"\n{'='*70}")
    print("  All questions complete.")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()