"""
Test the query understanding module with real questions.

Connects to Neo4j and Gemini, parses questions, and displays
the structured QueryPlan output.

Usage:
    python scripts/test_query_understanding.py
    python scripts/test_query_understanding.py --interactive
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# -- path setup --
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(_project_root / ".env")

from neo4j import GraphDatabase
from src.retrieval.query_understanding import QueryUnderstanding

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Test questions covering different query types
TEST_QUESTIONS = [
    # Entity-based, current state
    "Who does Sally Beck report to?",

    # Entity-based, point-in-time
    "Who did Sally Beck report to in March 2001?",

    # Entity-based, full history
    "Show me the complete reporting history for Sally Beck.",

    # Concept-based (no entity)
    "What concerns were raised about California energy prices?",

    # Multi-entity comparison
    "What is the relationship between Steven Kean and Jeff Dasovich?",

    # Ambiguous entity
    "Tell me about Smith.",

    # Organization query
    "Who works at Enron?",

    # Deal query
    "What decisions were made about the Mahonia deal?",

    # Time range
    "What happened between January and June 2001?",

    # Yes/no
    "Did Kenneth Lay know about the California situation?",
]


def display_query_plan(plan):
    """Pretty-print a QueryPlan for inspection."""
    print(f"\n{'='*70}")
    print(f"  Question:  {plan.raw_query}")
    print(f"{'='*70}")
    print(f"  Type:      {plan.question_type.value}")
    print(f"  Strategy:  {plan.retrieval_strategy.value}")
    print(f"  Clarify:   {plan.needs_clarification}", end="")
    if plan.clarification_reason:
        print(f" — {plan.clarification_reason}")
    else:
        print()

    # Entities
    if plan.entities:
        print(f"\n  Entities ({len(plan.entities)}):")
        for e in plan.entities:
            status = "RESOLVED" if e.canonical_id else "NOT FOUND"
            print(f"    [{status}] \"{e.raw_name}\" → {e.canonical_name or '???'}")
            print(f"             id={e.canonical_id or 'None'}")
            print(f"             type={e.entity_type}, confidence={e.confidence}")
            if e.alternatives:
                alt_names = [a.get("name", "?") for a in e.alternatives[:3]]
                print(f"             alternatives: {', '.join(alt_names)}")
    else:
        print("\n  Entities: none")

    # Time constraint
    tc = plan.time_constraint
    if tc.constraint_type.value != "none":
        print(f"\n  Time:      {tc.constraint_type.value}")
        if tc.date_from:
            print(f"             from: {tc.date_from}")
        if tc.date_to:
            print(f"             to:   {tc.date_to}")
        if tc.raw_reference:
            print(f"             ref:  \"{tc.raw_reference}\"")
    else:
        print(f"\n  Time:      none")

    # Claim types
    if plan.claim_types:
        print(f"  Claims:    {', '.join(plan.claim_types)}")

    # Semantic query
    if plan.semantic_query:
        print(f"  Semantic:  \"{plan.semantic_query}\"")

    print()


def run_batch_test(qu: QueryUnderstanding):
    """Run all test questions and display results."""
    print(f"\n{'#'*70}")
    print(f"  BATCH TEST — {len(TEST_QUESTIONS)} questions")
    print(f"{'#'*70}\n")

    results = {"graph": 0, "semantic": 0, "hybrid": 0, "clarify": 0}

    for i, question in enumerate(TEST_QUESTIONS, 1):
        print(f"[{i}/{len(TEST_QUESTIONS)}]", end=" ")
        try:
            plan = qu.parse_query(question)
            display_query_plan(plan)
            results[plan.retrieval_strategy.value] += 1
            if plan.needs_clarification:
                results["clarify"] += 1
        except Exception as e:
            print(f"  ERROR: {e}\n")

    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    print(f"  Graph strategy:    {results['graph']}")
    print(f"  Semantic strategy: {results['semantic']}")
    print(f"  Hybrid strategy:   {results['hybrid']}")
    print(f"  Need clarification:{results['clarify']}")
    print()


def run_interactive(qu: QueryUnderstanding):
    """Interactive mode — type questions and see QueryPlans."""
    print(f"\n{'#'*70}")
    print(f"  INTERACTIVE MODE — type a question (or 'quit' to exit)")
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
            display_query_plan(plan)
        except Exception as e:
            print(f"  ERROR: {e}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Test query understanding with real questions"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Enter interactive mode (type your own questions)",
    )
    args = parser.parse_args()

    # Connect to Neo4j
    logger.info("Connecting to Neo4j at %s", NEO4J_URI)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()

    # Initialize query understanding
    logger.info("Initializing query understanding...")
    qu = QueryUnderstanding(neo4j_driver=driver)

    try:
        if args.interactive:
            run_interactive(qu)
        else:
            run_batch_test(qu)
    finally:
        driver.close()


if __name__ == "__main__":
    main()