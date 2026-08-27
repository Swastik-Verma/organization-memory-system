"""
FastAPI application — entry point for the org memory system API.

Creates the app, manages service lifetimes (Neo4j, Qdrant,
QueryUnderstanding, RetrievalEngine), adds CORS for the frontend,
and registers all route modules.

Run with:
    python backend/scripts/run_server.py
    # or directly:
    uvicorn src.api.app:app --reload --port 8000
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_project_root / ".env")

from neo4j import GraphDatabase

from src.retrieval.qdrant_index import QdrantIndex
from src.retrieval.query_understanding import QueryUnderstanding
from src.retrieval.retrieval_engine import RetrievalEngine

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Lifespan — startup and shutdown
# ------------------------------------------------------------------ #

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage the lifetime of shared resources.

    On startup:
      - Connect to Neo4j
      - Connect to Qdrant and load embedding model
      - Initialize QueryUnderstanding (Gemini client)
      - Initialize RetrievalEngine

    On shutdown:
      - Close Neo4j driver

    All resources are stored on app.state so route handlers
    can access them via request.app.state.
    """
    # --- Startup ---
    logger.info("Starting up — connecting to services...")

    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")

    # Neo4j
    driver = GraphDatabase.driver(
        neo4j_uri, auth=(neo4j_user, neo4j_password)
    )
    driver.verify_connectivity()
    app.state.neo4j_driver = driver
    logger.info("Neo4j connected at %s", neo4j_uri)

    # Qdrant + embedding model
    qdrant = QdrantIndex(qdrant_url=qdrant_url)
    app.state.qdrant_index = qdrant
    logger.info("Qdrant connected at %s", qdrant_url)

    # Query understanding (Gemini)
    query_understanding = QueryUnderstanding(
        neo4j_driver=driver,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
    )
    app.state.query_understanding = query_understanding
    logger.info("QueryUnderstanding initialized")

    # Retrieval engine
    retrieval_engine = RetrievalEngine(
        neo4j_driver=driver,
        qdrant_index=qdrant,
    )
    app.state.retrieval_engine = retrieval_engine
    logger.info("RetrievalEngine initialized")

    logger.info("All services ready.")

    yield  # --- App runs here ---

    # --- Shutdown ---
    logger.info("Shutting down — closing connections...")
    driver.close()
    logger.info("Neo4j connection closed.")


# ------------------------------------------------------------------ #
# App creation
# ------------------------------------------------------------------ #

app = FastAPI(
    title="Organizational Memory System",
    description=(
        "API for querying an organizational knowledge graph built from "
        "the Enron email corpus. Supports natural language questions, "
        "entity exploration, graph traversal, and evidence retrieval."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ------------------------------------------------------------------ #
# CORS — allow the React frontend to call us
# ------------------------------------------------------------------ #

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # React dev server (CRA)
        "http://localhost:5173",   # Vite dev server
        "http://localhost:5174",   # Vite alternate port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ #
# Register route modules
# ------------------------------------------------------------------ #

from src.api.routes import chat, entities, graph, evidence, health, admin

app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(entities.router, prefix="/api", tags=["Entities"])
app.include_router(graph.router, prefix="/api", tags=["Graph"])
app.include_router(evidence.router, prefix="/api", tags=["Evidence"])
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(admin.router, prefix="/api", tags=["Admin"])


# ------------------------------------------------------------------ #
# Root endpoint
# ------------------------------------------------------------------ #

@app.get("/")
async def root():
    """Root endpoint — confirms the API is running."""
    return {
        "service": "Organizational Memory System",
        "version": "1.0.0",
        "docs": "/docs",
    }