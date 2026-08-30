"""
Conversation memory and follow-up resolution for multi-turn chat.

Two responsibilities:
  1. ConversationMemory — stores the last N question-answer pairs
     per session, so the chatbot has context for follow-ups.
  2. FollowUpResolver — detects when a new question is a follow-up
     (pronouns, "what about", missing entities) and rewrites it
     into a standalone question using a lightweight LLM call.

Design decisions:
  - Memory is stored in-process (dict of session_id → list[Turn]).
    This is fine for a single-server portfolio demo. Production
    would use Redis or a database.
  - Bounded window (default 5 turns) prevents context from growing
    unboundedly and blowing out token costs.
  - Follow-up detection uses a cheap heuristic first (regex for
    pronouns/references), then only calls the LLM if the heuristic
    fires. This avoids burning an API call on every standalone question.
  - The rewriting prompt is separate from the chatbot's answer prompt
    and uses gemini-3.1-flash-lite (fast, cheap) since it's a simple
    text transformation, not a complex reasoning task.
"""

import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig

from src.chatbot.prompts import FOLLOW_UP_REWRITE_PROMPT

_project_root = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_project_root / ".env")

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Data classes
# ------------------------------------------------------------------ #

@dataclass
class Turn:
    """One question-answer pair in a conversation."""
    question: str
    rewritten_question: Optional[str]  # the standalone version, if rewritten
    answer: str
    entities_mentioned: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ------------------------------------------------------------------ #
# Conversation Memory
# ------------------------------------------------------------------ #

class ConversationMemory:
    """
    Stores bounded conversation history per session.

    Each session is identified by a session_id (UUID string).
    Stores the last `max_turns` question-answer pairs.

    In-memory storage (dict) — suitable for single-server demo.
    Production would use Redis with TTL-based expiry.
    """

    def __init__(self, max_turns: int = 5):
        """
        Args:
            max_turns: maximum number of turns to keep per session.
                       Older turns are dropped when the limit is exceeded.
        """
        self.max_turns = max_turns
        self._sessions: dict[str, list[Turn]] = {}
        logger.info(
            "ConversationMemory initialized — max_turns=%d", max_turns
        )

    def create_session(self) -> str:
        """Create a new conversation session and return its ID."""
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = []
        return session_id

    def get_history(self, session_id: str) -> list[Turn]:
        """Get the conversation history for a session."""
        return self._sessions.get(session_id, [])

    def add_turn(
        self,
        session_id: str,
        question: str,
        rewritten_question: Optional[str],
        answer: str,
        entities_mentioned: Optional[list[str]] = None,
    ):
        """
        Add a new turn to a session's history.

        If the session doesn't exist, creates it automatically.
        If history exceeds max_turns, drops the oldest turn.
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = []

        turn = Turn(
            question=question,
            rewritten_question=rewritten_question,
            answer=answer,
            entities_mentioned=entities_mentioned or [],
        )

        self._sessions[session_id].append(turn)

        # Trim to bounded window
        if len(self._sessions[session_id]) > self.max_turns:
            self._sessions[session_id] = (
                self._sessions[session_id][-self.max_turns:]
            )

    def format_history_for_prompt(self, session_id: str) -> str:
        """
        Format conversation history as text for the LLM prompt.

        Used by the follow-up resolver to give the LLM context
        about what was previously discussed.
        """
        history = self.get_history(session_id)
        if not history:
            return ""

        parts = []
        for i, turn in enumerate(history, 1):
            q = turn.rewritten_question or turn.question
            # Truncate long answers to save tokens
            answer_preview = turn.answer[:300]
            if len(turn.answer) > 300:
                answer_preview += "..."
            parts.append(f"Turn {i}:")
            parts.append(f"  Q: {q}")
            parts.append(f"  A: {answer_preview}")

        return "\n".join(parts)

    def get_recent_entities(self, session_id: str) -> list[str]:
        """
        Get entity names mentioned in recent turns.

        Used as a hint for the follow-up resolver — if the user
        says "his manager", the resolver can check which person
        was discussed recently.
        """
        history = self.get_history(session_id)
        entities = []
        # Most recent turns first
        for turn in reversed(history):
            for entity in turn.entities_mentioned:
                if entity not in entities:
                    entities.append(entity)
        return entities[:10]  # cap to avoid bloat

    @property
    def active_sessions(self) -> int:
        """Number of active conversation sessions."""
        return len(self._sessions)


# ------------------------------------------------------------------ #
# Follow-up Detection (heuristic)
# ------------------------------------------------------------------ #

# Patterns that suggest the question is a follow-up, not standalone
_FOLLOW_UP_PATTERNS = [
    # Pronouns referring to a previous entity
    r"\b(he|she|they|him|her|them|his|their|its|it)\b",
    # Explicit references to previous discussion
    r"\b(that person|that deal|that decision|the same)\b",
    # "What about" / "How about" / "And" openers
    r"^(what about|how about|and what|and who|and when|what if)\b",
    # Very short questions that only make sense as follow-ups
    # e.g. "In 2001?" or "Before the collapse?"
    r"^(in \d{4}|before |after |during |since |until )",
    # "Also" / "too" / "as well" suggesting continuation
    r"\b(also|too|as well|in addition|furthermore)\b",
]

_FOLLOW_UP_REGEX = re.compile(
    "|".join(_FOLLOW_UP_PATTERNS), re.IGNORECASE
)


def is_likely_follow_up(question: str, has_history: bool) -> bool:
    """
    Quick heuristic: does this question look like a follow-up?

    Only returns True if there IS conversation history to refer back to.
    A question with pronouns but no history is just a badly-formed
    standalone question, not a follow-up.
    """
    if not has_history:
        return False

    return bool(_FOLLOW_UP_REGEX.search(question))


# ------------------------------------------------------------------ #
# Follow-up Resolver (LLM-based rewriting)
# ------------------------------------------------------------------ #

class FollowUpResolver:
    """
    Rewrites follow-up questions into standalone questions.

    When a user asks "What about in 2001?", the resolver reads the
    conversation history and produces "Who did Sally Beck report to
    in 2001?" — a complete question the retrieval pipeline can handle.

    Uses gemini-3.1-flash-lite for rewriting (fast, cheap — this is
    a simple text transformation, not complex reasoning).
    """

    def __init__(self, gemini_model: str = "gemini-3.1-flash-lite"):
        self.model_name = gemini_model
        self.client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY", ""),
        )
        logger.info(
            "FollowUpResolver initialized — model=%s", self.model_name
        )

    def resolve(
        self,
        question: str,
        history_text: str,
        recent_entities: list[str],
    ) -> str:
        """
        Rewrite a follow-up question into a standalone question.

        Args:
            question: the user's raw follow-up (e.g. "What about in 2001?")
            history_text: formatted conversation history
            recent_entities: entity names from recent turns

        Returns:
            A standalone question (e.g. "Who did Sally Beck report to in 2001?")
            If rewriting fails, returns the original question unchanged.
        """
        entity_hint = ""
        if recent_entities:
            entity_hint = (
                f"\nEntities from recent discussion: "
                f"{', '.join(recent_entities[:5])}"
            )

        user_message = f"""CONVERSATION HISTORY:
{history_text}
{entity_hint}

NEW QUESTION: {question}

Rewrite the new question as a complete, standalone question."""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_message,
                config=GenerateContentConfig(
                    system_instruction=FOLLOW_UP_REWRITE_PROMPT,
                    temperature=0.0,
                    thinking_config=ThinkingConfig(thinking_budget=0),
                ),
            )

            rewritten = response.text.strip()

            # Sanity check: the rewritten question should be longer or
            # similar length to the original, and should be a question
            if len(rewritten) < 5 or len(rewritten) > 500:
                logger.warning(
                    "Rewrite produced suspicious length (%d), "
                    "using original",
                    len(rewritten),
                )
                return question

            logger.info(
                "Follow-up resolved: '%s' → '%s'",
                question, rewritten,
            )
            return rewritten

        except Exception as e:
            logger.error("Follow-up resolution failed: %s", e)
            return question  # graceful fallback — use original