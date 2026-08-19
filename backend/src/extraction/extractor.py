"""
extractor.py

Single-email extraction logic: takes one parsed email, sends it to
Gemini, validates the structured response, and returns a fully-formed
ExtractionResult (with the real message_id injected).

This is the reusable core that batch_extract.py (Step 6) will call
in a loop across thousands of emails.
"""

import json
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

from src.extraction.prompts import build_prompt
from src.extraction.schema import ExtractionResult, LLMExtractionOutput

load_dotenv()

MODEL_NAME = "gemini-3.1-flash-lite"

# Client is created once, at module load, and reused across every call —
# creating a new client per email would be wasteful and unnecessary.
_client = genai.Client(
    vertexai=True,
    project="project-997e2e49-1066-436c-9d7",
    location="global",
)


class ExtractionError(Exception):
    """Raised when extraction fails for a specific email, so the batch
    script can catch this distinctly from a Pydantic validation error."""
    pass


def extract_from_email(record: dict) -> ExtractionResult:
    """
    Runs Gemini extraction on a single parsed email record.

    Args:
        record: a dict loaded from one line of parsed_emails.jsonl
                (must contain message_id, from_addr, to_addrs, subject, body)

    Returns:
        A validated ExtractionResult with the real message_id attached.

    Raises:
        ExtractionError: if the API call fails or the response can't
        be parsed/validated, wrapping the original exception for context.
    """
    prompt = build_prompt(
        from_addr=record["from_addr"],
        to_addrs=record["to_addrs"],
        subject=record["subject"],
        body=record["body"],
    )

    try:
        response = _client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LLMExtractionOutput,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
    except Exception as e:
        # Covers network errors, 429 rate limit errors, Gemini server
        # errors, etc. We don't try to distinguish these here — the
        # batch script (Step 6) will decide how to react based on
        # the error message (e.g. pause longer on a 429).
        raise ExtractionError(f"Gemini API call failed: {e}") from e

    try:
        # strict=False allows literal newlines/control chars inside JSON
        # strings — Gemini emits these when quoting verbatim from
        # hard-wrapped email bodies for the `evidence` field.
        data = json.loads(response.text, strict=False)
        llm_output = LLMExtractionOutput.model_validate(data)
    except Exception as e:
        # Covers cases where Gemini returned something that technically
        # isn't valid JSON, or doesn't match our schema shape — rare
        # with response_schema enforced, but not impossible.
        raise ExtractionError(f"Failed to validate Gemini response: {e}") from e

    # Inject the real message_id ourselves — never trust the model to
    # supply this (see Step 3 findings).
    return ExtractionResult(
        message_id=record["message_id"],
        **llm_output.model_dump()
    )