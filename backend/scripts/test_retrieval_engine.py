"""
Test the retrieval engine with real questions end-to-end.

Runs query understanding → retrieval engine → displays context pack.

Usage:
    python scripts/test_retrieval_engine.py
    python scripts/test_retrieval_engine.py --interactive
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root / "backend"))

from dotenv import load_dotenv
load_dotenv(_project_root / ".env")

from neo4j import GraphDatabase
from src.retrieval.query_understanding import QueryUnderstanding
from src.retrieval.qdrant_index import QdrantIndex
from src.retrieval.retrieval_engine import RetrievalEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

TEST_QUESTIONS = [
    # Graph-friendly: entity + current state
    "Who does Sally Beck report to?",

    # Graph-friendly: entity + point-in-time
    "Who did Sally Beck report to in March 2001?",

    # Graph-friendly: full history
    "Show me the complete reporting history for Sally Beck.",

    # Semantic-friendly: concept query
    "What concerns were raised about California energy prices?",

    # Hybrid: entity + concept
    "What is the relationship between Steven Kean and Jeff Dasovich?",

    # Semantic fallback: entity not found
    "What decisions were made about the Mahonia deal?",
]


def display_context_pack(pack):
    """Pretty-print a ContextPack."""
    print(f"\n{'='*70}")
    print(f"  Question: {pack.query_plan.raw_query}")
    print(f"{'='*70}")

    m = pack.metadata
    print(f"  Strategy:  {m.strategy_used}")
    print(f"  Results:   {m.total_results} (graph={m.graph_results_count}, "
          f"semantic={m.semantic_results_count}, merged={m.merged_count})")
    print(f"  Time:      {m.retrieval_time_ms:.0f}ms")

    if pack.clarification:
        print(f"\n  CLARIFICATION: {pack.clarification.message}")
        if pack.clarification.options:
            for opt in pack.clarification.options[:5]:
                print(f"    - {opt.get('name', '?')} ({opt.get('type', '?')})")

    if pack.entities:
        print(f"\n  Entities:")
        for e in pack.entities:
            print(f"    {e.get('name', '?')} [{e.get('type', '?')}] "
                  f"({e.get('mention_count', 0)} mentions)")

    if pack.claims:
        print(f"\n  Claims ({len(pack.claims)}):")
        for i, claim in enumerate(pack.claims[:8], 1):
            print(f"\n    [{i}] {claim.subject_name} {claim.claim_type} "
                  f"{claim.object_name}")
            print(f"        confidence={claim.confidence:.2f}  "
                  f"score={claim.composite_score:.3f}  "
                  f"source={claim.source}")
            print(f"        valid: {claim.valid_from or '?'} → "
                  f"{claim.valid_to or 'present'}  "
                  f"status={claim.status or '?'}")

            for j, ev in enumerate(claim.evidence[:2], 1):
                quote = ev.get("quote", "")
                if len(quote) > 80:
                    quote = quote[:77] + "..."
                print(f"        evidence {j}: \"{quote}\"")
    else:
        print(f"\n  No claims retrieved.")

    print()


def run_batch_test(qu, engine):
    """Run all test questions and display results."""
    print(f"\n{'#'*70}")
    print(f"  RETRIEVAL ENGINE — END-TO-END TEST")
    print(f"{'#'*70}\n")

    for i, question in enumerate(TEST_QUESTIONS, 1):
        print(f"[{i}/{len(TEST_QUESTIONS)}]", end="")

        try:
            plan = qu.parse_query(question)
            pack = engine.retrieve(plan, user_clearance=4)
            display_context_pack(pack)
        except Exception as e:
            print(f"  ERROR: {e}\n")
            import traceback
            traceback.print_exc()

        time.sleep(1)  # respect Gemini rate limits


def run_interactive(qu, engine):
    """Interactive mode."""
    print(f"\n{'#'*70}")
    print(f"  INTERACTIVE MODE — type a question (or 'quit')")
    print(f"{'#'*70}\n")

    while True:
        try:
            question = input("Question> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not question or question.lower() in ("quit", "exit", "q"):
            break

        try:
            plan = qu.parse_query(question)
            pack = engine.retrieve(plan, user_clearance=4)
            display_context_pack(pack)

            # Also show the LLM-ready context
            print("--- LLM Context Preview ---")
            llm_ctx = engine.format_context_for_llm(pack)
            # Show first 1000 chars
            if len(llm_ctx) > 1000:
                print(llm_ctx[:1000] + "\n... (truncated)")
            else:
                print(llm_ctx)
            print("--- End Preview ---\n")

        except Exception as e:
            print(f"  ERROR: {e}\n")
            import traceback
            traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(
        description="Test retrieval engine end-to-end"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Enter interactive mode",
    )
    args = parser.parse_args()

    # Connect to services
    logger.info("Connecting to Neo4j at %s", NEO4J_URI)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()

    logger.info("Connecting to Qdrant at %s", QDRANT_URL)
    qdrant = QdrantIndex(qdrant_url=QDRANT_URL)

    logger.info("Initializing query understanding...")
    qu = QueryUnderstanding(neo4j_driver=driver)

    logger.info("Initializing retrieval engine...")
    engine = RetrievalEngine(neo4j_driver=driver, qdrant_index=qdrant)

    try:
        if args.interactive:
            run_interactive(qu, engine)
        else:
            run_batch_test(qu, engine)
    finally:
        driver.close()


if __name__ == "__main__":
    main()