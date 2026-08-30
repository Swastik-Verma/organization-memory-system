"""
FastAPI dependencies — shared resources and authentication.

These functions are injected into route handlers via Depends().
Each route gets the shared Neo4j driver, Qdrant index, or
authenticated user without creating new connections.

Authentication is simplified for the portfolio demo:
  - Reads X-User-Clearance header (1-4)
  - Defaults to clearance 1 (intern) if missing
  - A production app would use JWT tokens instead
"""

from dataclasses import dataclass
from typing import Optional
from src.chatbot.chatbot import Chatbot
from src.chatbot.conversation import ConversationMemory, FollowUpResolver

from fastapi import Depends, Header, Request

from src.retrieval.qdrant_index import QdrantIndex
from src.retrieval.query_understanding import QueryUnderstanding
from src.retrieval.retrieval_engine import RetrievalEngine


# ------------------------------------------------------------------ #
# User model
# ------------------------------------------------------------------ #

@dataclass
class CurrentUser:
    """Represents the authenticated user making the request."""
    clearance: int       # 1=intern, 2=analyst, 3=manager, 4=executive
    username: str        # display name


# ------------------------------------------------------------------ #
# Service dependencies
# ------------------------------------------------------------------ #

def get_neo4j_driver(request: Request):
    """Get the shared Neo4j driver from app state."""
    return request.app.state.neo4j_driver


def get_qdrant_index(request: Request) -> QdrantIndex:
    """Get the shared QdrantIndex from app state."""
    return request.app.state.qdrant_index


def get_query_understanding(request: Request) -> QueryUnderstanding:
    """Get the shared QueryUnderstanding from app state."""
    return request.app.state.query_understanding


def get_retrieval_engine(request: Request) -> RetrievalEngine:
    """Get the shared RetrievalEngine from app state."""
    return request.app.state.retrieval_engine

def get_chatbot(request: Request) -> "Chatbot":
    """Get the shared Chatbot from app state."""
    return request.app.state.chatbot

def get_conversation_memory(request: Request) -> ConversationMemory:
    \"\"\"Get the shared ConversationMemory from app state.\"\"\"
    return request.app.state.conversation_memory

def get_follow_up_resolver(request: Request) -> FollowUpResolver:
    \"\"\"Get the shared FollowUpResolver from app state.\"\"\"
    return request.app.state.follow_up_resolver



# ------------------------------------------------------------------ #
# Authentication
# ------------------------------------------------------------------ #

# Simplified user database for portfolio demo.
# In production this would be a real user store + JWT validation.
DEMO_USERS = {
    "1": CurrentUser(clearance=1, username="intern"),
    "2": CurrentUser(clearance=2, username="analyst"),
    "3": CurrentUser(clearance=3, username="manager"),
    "4": CurrentUser(clearance=4, username="executive"),
}


def get_current_user(
    x_user_clearance: Optional[str] = Header(default=None),
) -> CurrentUser:
    """
    Extract the current user from the request headers.

    Simplified auth for portfolio demo:
      - Send X-User-Clearance: 1-4 to set clearance level
      - Default: clearance 4 (executive) if header is missing
        (makes demo easier — no auth needed to see everything)

    In production:
      - Parse JWT from Authorization: Bearer <token>
      - Validate signature, expiry, and extract user claims
      - Look up clearance from user database
    """
    if x_user_clearance and x_user_clearance in DEMO_USERS:
        return DEMO_USERS[x_user_clearance]

    # Default to executive clearance for easy demo
    return CurrentUser(clearance=4, username="demo_user")