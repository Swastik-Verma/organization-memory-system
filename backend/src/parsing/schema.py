"""
schema.py

Defines the ParsedEmail data model: the validated, structured shape
that every parsed Enron email must conform to.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator
from email.utils import parsedate_to_datetime


class ParsedEmail(BaseModel):
    """
    Structured representation of a single parsed email.

    This is the contract between the parsing layer and everything
    downstream (extraction, dedup, graph storage). If an email can't
    be validated into this shape, it should be flagged as a parsing
    failure rather than silently passed along.
    """

    message_id: str
    from_addr: str
    to_addrs: list[str]
    cc_addrs: list[str] = []
    subject: str = ""
    date: Optional[datetime] = None
    body: str
    x_folder: str = ""
    x_origin: str = ""

    @field_validator("date", mode="before")
    @classmethod
    def parse_email_date(cls, value):
        """
        Email dates arrive as raw strings like:
        'Mon, 14 May 2001 16:39:00 -0700 (PDT)'

        Pydantic doesn't know how to parse that format by default,
        so we convert it ourselves using email.utils.parsedate_to_datetime,
        which is built specifically for RFC 2822 email date formats.

        If the date is missing or malformed, we return None instead of
        crashing — a bad date shouldn't block the whole email from
        being stored; we just flag it as unknown.
        """
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None