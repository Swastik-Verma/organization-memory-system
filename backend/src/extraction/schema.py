"""
schema.py (extraction)

Defines the structured shape of what Gemini must return when extracting
knowledge from a single email. This is both the contract we validate
Gemini's output against, and the basis for the prompt we send it.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ExtractedPerson(BaseModel):
    """A person mentioned in the email — not just sender/recipient,
    but anyone referenced by name in the body too."""
    name: str = Field(description="Full name as it appears in the email")
    email: Optional[str] = Field(default=None, description="Email address if mentioned or known")
    role_or_title: Optional[str] = Field(default=None, description="Job title or role, if mentioned")


class ExtractedOrganization(BaseModel):
    """A company, division, or department mentioned in the email."""
    name: str
    org_type: Optional[str] = Field(default=None, description="e.g. 'company', 'internal division', 'government body'")


class ExtractedDeal(BaseModel):
    """A named business initiative, project, or transaction."""
    name: str
    description: Optional[str] = Field(default=None, description="Brief description of what the deal/project involves")
    parties_involved: list[str] = Field(default_factory=list, description="Names of people or orgs involved")


class ExtractedDecision(BaseModel):
    """A decision, commitment, or action item stated in the email."""
    description: str = Field(description="What was decided or committed to")
    made_by: Optional[str] = Field(default=None, description="Who made this decision/commitment, if clear")
    affects: list[str] = Field(default_factory=list, description="Who or what this decision affects")


class ExtractedRelationship(BaseModel):
    """An implied relationship between two people mentioned in the email."""
    person_a: str
    person_b: str
    relationship_type: str = Field(description="e.g. 'reports_to', 'works_with', 'negotiating_with'")
    evidence: Optional[str] = Field(default=None, description="Short snippet or reason supporting this relationship")

class LLMExtractionOutput(BaseModel):
    """
    The schema we actually send to Gemini as response_schema.
    Deliberately excludes message_id — Gemini has no reliable way to
    know the true message_id, so asking it to produce one just invites
    hallucination. We inject the real message_id ourselves afterward.
    """
    people: list[ExtractedPerson] = Field(default_factory=list)
    organizations: list[ExtractedOrganization] = Field(default_factory=list)
    deals: list[ExtractedDeal] = Field(default_factory=list)
    decisions: list[ExtractedDecision] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """
    Top-level container for everything extracted from one email.
    Tied back to the source email via message_id — this is what
    preserves the 'evidence trail' the project is built around.
    """
    message_id: str
    people: list[ExtractedPerson] = Field(default_factory=list)
    organizations: list[ExtractedOrganization] = Field(default_factory=list)
    deals: list[ExtractedDeal] = Field(default_factory=list)
    decisions: list[ExtractedDecision] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
    
    # Extraction versioning
    prompt_version: str = ""       # hash of the prompt that produced this extraction
    model_name: str = ""           # model used (e.g. "gemini-3.1-flash-lite")