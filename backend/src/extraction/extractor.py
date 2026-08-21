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


def _call_llm_repair(self, repair_prompt: str):
    """Send a repair request to the LLM to fix structural errors."""
    response = self.client.models.generate_content(
        model=self.model_name,
        contents=repair_prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": LLMExtractionOutput,
            "thinking_config": ThinkingConfig(thinking_budget=0),
        },
    )
    return response

def extract_with_repair(self, email_body: str, message_id: str,
                        max_repairs: int = 2) -> ExtractionResult:
    """
    Extract entities from an email, with a repair loop for validation failures.
    
    If the LLM returns structurally invalid output, sends the error message
    back and asks for a fix. Tries up to max_repairs times before giving up.
    
    Also stores the raw LLM response for debugging.

    And
    
    The raw response storage applies to all future extractions. Existing 10k 
    extractions don't have raw responses stored; if any need debugging, re-extract
    that single email and the raw response will be saved.
    """
    raw_responses_dir = Path(__file__).parent.parent.parent.parent / "data" / "processed" / "raw_responses"
    raw_responses_dir.mkdir(exist_ok=True)
    
    # First attempt — normal extraction
    response = self._call_llm(email_body)
    raw_text = response.text
    
    # Save raw response for debugging
    safe_id = message_id.replace("/", "_").replace("<", "").replace(">", "")[:100]
    raw_path = raw_responses_dir / f"{safe_id}.json"
    raw_path.write_text(raw_text)
    
    # Try to parse and validate
    for attempt in range(max_repairs + 1):
        try:
            data = json.loads(raw_text, strict=False)
            result = LLMExtractionOutput.model_validate(data)
            return ExtractionResult(message_id=message_id, **result.model_dump())
        
        except (json.JSONDecodeError, ValidationError) as e:
            if attempt >= max_repairs:
                raise ExtractionError(
                    f"Failed after {max_repairs} repair attempts: {e}",
                    message_id=message_id
                ) from e
            
            # Send the error back to the LLM and ask for a fix
            repair_prompt = (
                f"Your previous response had a structural error:\n"
                f"{str(e)[:500]}\n\n"
                f"Here was your response:\n"
                f"{raw_text[:2000]}\n\n"
                f"Please fix the structural error and return valid JSON "
                f"matching the required schema. Return ONLY the corrected JSON."
            )
            
            repair_response = self._call_llm_repair(repair_prompt)
            raw_text = repair_response.text
            
            # Save repair attempt
            repair_path = raw_responses_dir / f"{safe_id}_repair_{attempt+1}.json"
            repair_path.write_text(raw_text)


