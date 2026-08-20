"""
test_parsing.py

Unit tests for the ingestion layer: email parser, noise detector,
and thread reconstructor.

Run with:
    cd ~/Layer_10_Project2/backend
    python -m pytest ../tests/test_parsing.py -v
"""

import pytest
from datetime import datetime
from src.parsing.schema import ParsedEmail
from src.parsing.noise_detector import (
    detect_noise_regions,
    is_in_noise,
    get_original_content,
)

from src.parsing.thread_reconstructor import normalize_subject


# ===================================================================
# ParsedEmail schema tests
# ===================================================================

class TestParsedEmailSchema:
    """Tests for the ParsedEmail Pydantic model."""

    def test_valid_email_minimal(self):
        """Minimum required fields produce a valid ParsedEmail."""
        email = ParsedEmail(
            message_id="<test123@enron.com>",
            from_addr="john@enron.com",
            to_addrs=["jane@enron.com"],
            body="Hello, this is a test email."
        )
        assert email.message_id == "<test123@enron.com>"
        assert email.from_addr == "john@enron.com"
        assert email.subject == ""  # default
        assert email.date is None   # default

    def test_valid_date_parsing(self):
        """RFC 2822 date string is parsed into datetime."""
        email = ParsedEmail(
            message_id="<test@enron.com>",
            from_addr="john@enron.com",
            to_addrs=[],
            body="test",
            date="Mon, 14 May 2001 16:39:00 -0700 (PDT)"
        )
        assert isinstance(email.date, datetime)
        assert email.date.year == 2001
        assert email.date.month == 5

    def test_out_of_range_date_becomes_none(self):
        """Dates outside 1995-2005 are treated as null."""
        email = ParsedEmail(
            message_id="<test@enron.com>",
            from_addr="john@enron.com",
            to_addrs=[],
            body="test",
            date="Tue, 31 Dec 1979 23:59:00 -0000"
        )
        assert email.date is None

    def test_malformed_date_becomes_none(self):
        """Unparseable date strings return None, not an error."""
        email = ParsedEmail(
            message_id="<test@enron.com>",
            from_addr="john@enron.com",
            to_addrs=[],
            body="test",
            date="not a real date"
        )
        assert email.date is None

    def test_empty_optional_fields(self):
        """Optional fields default correctly."""
        email = ParsedEmail(
            message_id="<test@enron.com>",
            from_addr="john@enron.com",
            to_addrs=[],
            body="test"
        )
        assert email.cc_addrs == []
        assert email.x_folder == ""
        assert email.x_origin == ""
        assert email.in_reply_to is None
        assert email.references == []
        assert email.x_from_display is None


# ===================================================================
# Noise detector tests
# ===================================================================

class TestNoiseDetector:
    """Tests for noise region detection."""

    def test_no_noise_in_clean_email(self):
        """A plain email with no quotes or signatures returns no regions."""
        body = "Hi team,\n\nPlease review the attached document.\n\nThanks,\nJohn"
        regions = detect_noise_regions(body)
        assert len(regions) == 0

    def test_detects_forwarding_header(self):
        """-----Original Message----- is detected as noise."""
        body = (
            "Sounds good, let's proceed.\n\n"
            "-----Original Message-----\n"
            "From: John Lavorato\n"
            "Sent: March 10, 2001\n"
            "Subject: Trading desk\n\n"
            "I think we should assign Sally."
        )
        regions = detect_noise_regions(body)
        assert len(regions) >= 1
        forward_regions = [r for r in regions if r.region_type == "forward_header"]
        assert len(forward_regions) == 1
        # The noise should start at the "-----" line
        assert body[forward_regions[0].start:].startswith("-----")

    def test_detects_quoted_reply_with_angle_brackets(self):
        """> quoted lines are detected as noise."""
        body = (
            "I agree with your proposal.\n\n"
            "> I think we should move forward\n"
            "> with the West Coast plan.\n"
            "> Let me know your thoughts.\n"
        )
        regions = detect_noise_regions(body)
        quoted = [r for r in regions if r.region_type == "quoted_reply"]
        assert len(quoted) >= 1

    def test_detects_wrote_pattern(self):
        """'On ... wrote:' lines are detected as quote introducers."""
        body = (
            "Sounds good.\n\n"
            "On March 10, John wrote:\n"
            "> We should finalize the deal.\n"
            "> Please review the terms.\n"
        )
        regions = detect_noise_regions(body)
        assert len(regions) >= 1

    def test_is_in_noise_true(self):
        """A span inside a noise region returns True."""
        body = (
            "Original content here.\n\n"
            "-----Original Message-----\n"
            "This is forwarded content about Sally Beck."
        )
        regions = detect_noise_regions(body)
        # "Sally Beck" is in the forwarded part
        sally_pos = body.find("Sally Beck")
        assert is_in_noise(sally_pos, sally_pos + 10, regions) is True

    def test_is_in_noise_false(self):
        """A span in original content returns False."""
        body = (
            "Original content here.\n\n"
            "-----Original Message-----\n"
            "This is forwarded content."
        )
        regions = detect_noise_regions(body)
        assert is_in_noise(0, 22, regions) is False

    def test_empty_body(self):
        """Empty body returns no regions."""
        assert detect_noise_regions("") == []
        assert detect_noise_regions(None) == []

    def test_get_original_content_strips_noise(self):
        """get_original_content returns only non-noise text."""
        body = (
            "Please review this.\n\n"
            "-----Original Message-----\n"
            "From: John\n"
            "Old content here."
        )
        regions = detect_noise_regions(body)
        original = get_original_content(body, regions)
        assert "Please review this" in original
        assert "Old content here" not in original


# ===================================================================
# Thread reconstructor tests (subject normalization)
# ===================================================================

class TestThreadReconstructor:
    """Tests for subject normalization used in threading."""

    def test_strips_single_re(self):
        assert normalize_subject("Re: Trading desk update") == "trading desk update"

    def test_strips_multiple_re(self):
        assert normalize_subject("Re: Re: Re: Trading desk update") == "trading desk update"

    def test_strips_fw(self):
        assert normalize_subject("Fw: Meeting notes") == "meeting notes"

    def test_strips_fwd(self):
        assert normalize_subject("Fwd: Budget proposal") == "budget proposal"

    def test_strips_mixed_prefixes(self):
        assert normalize_subject("Re: Fw: Re: Trading desk update") == "trading desk update"

    def test_no_prefix(self):
        assert normalize_subject("Trading desk update") == "trading desk update"

    def test_empty_subject(self):
        assert normalize_subject("") == ""

    def test_none_subject(self):
        assert normalize_subject(None) == ""

    def test_case_insensitive(self):
        assert normalize_subject("RE: RE: Hello") == "hello"
        assert normalize_subject("FW: Hello") == "hello"