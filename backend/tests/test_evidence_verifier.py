# tests/test_evidence_verifier.py
import pytest
from src.extraction.evidence_verifier import (
    normalize_whitespace,
    build_offset_map,
    find_quote_in_body,
)


class TestNormalizeWhitespace:
    def test_collapses_newlines(self):
        assert normalize_whitespace("hello\nworld") == "hello world"

    def test_collapses_multiple_spaces(self):
        assert normalize_whitespace("hello    world") == "hello world"

    def test_collapses_tabs(self):
        assert normalize_whitespace("hello\t\tworld") == "hello world"

    def test_strips_leading_trailing(self):
        assert normalize_whitespace("  hello  ") == "hello"

    def test_mixed_whitespace(self):
        assert normalize_whitespace("hello\n  \t  world") == "hello world"

    def test_empty_string(self):
        assert normalize_whitespace("") == ""


class TestBuildOffsetMap:
    def test_no_whitespace(self):
        # "abc" → offset_map should be [0, 1, 2]
        m = build_offset_map("abc")
        assert m == [0, 1, 2]

    def test_single_space(self):
        # "a b" → normalized is "a b", offset_map [0, 1, 2]
        m = build_offset_map("a b")
        assert m == [0, 1, 2]

    def test_newline_between_words(self):
        # "a\nb" → normalized is "a b" (3 chars)
        # offset_map: a→0, \n→1 (first whitespace), b→2
        m = build_offset_map("a\nb")
        assert len(m) == 3
        assert m[0] == 0  # 'a' at original pos 0
        assert m[1] == 1  # the \n (collapsed to space) at original pos 1
        assert m[2] == 2  # 'b' at original pos 2

    def test_multiple_whitespace_collapses(self):
        # "a  \n  b" → normalized "a b" (3 chars)
        # Only the first whitespace char in the run gets an entry
        m = build_offset_map("a  \n  b")
        assert len(m) == 3
        assert m[0] == 0  # 'a'
        assert m[1] == 1  # first space in the run "  \n  "
        assert m[2] == 6  # 'b' is at original position 6

    def test_leading_whitespace(self):
        # "  a" → normalized "a" (1 char after strip... but build_offset_map
        # doesn't strip — it just collapses. So normalized is " a" (2 chars))
        # Actually, build_offset_map builds the map for collapse, not strip.
        # The stripping happens in normalize_whitespace(). The offset map
        # reflects what collapse does before stripping.
        m = build_offset_map("  a")
        # "  a" collapses to " a" → 2 chars
        assert len(m) == 2
        assert m[0] == 0   # first space
        assert m[1] == 2   # 'a'

    def test_trailing_whitespace(self):
        m = build_offset_map("a  ")
        # "a  " collapses to "a " → 2 chars
        assert len(m) == 2
        assert m[0] == 0  # 'a'
        assert m[1] == 1  # first space in trailing run

    def test_empty_string(self):
        m = build_offset_map("")
        assert m == []

    def test_body_with_leading_spaces(self):
        body = "   hello world"  # 3 leading spaces
        quote = "hello"

        result = find_quote_in_body(quote, body)

        # 'h' is at index 3 in the original body ("   hello world")
        assert result[0] == 3  # THIS WILL FAIL with your current implementation!

class TestFindQuoteInBody:
    def test_exact_match(self):
        result = find_quote_in_body("hello world", "hello world")
        assert result is not None
        assert result[0] == 0


    def test_match_with_newline_in_body(self):
        body = "please review the attached\ncontract by Friday"
        quote = "review the attached contract"
        result = find_quote_in_body(quote, body)
        assert result is not None
        # char_start should point to 'r' in 'review' in the original
        assert body[result[0]] == 'r'

    def test_no_match(self):
        result = find_quote_in_body("completely different text", "hello world")
        assert result is None

    def test_case_insensitive_fallback(self):
        result = find_quote_in_body("HELLO WORLD", "hello world")
        assert result is not None

    def test_empty_quote(self):
        result = find_quote_in_body("", "hello world")
        assert result is None

    def test_empty_body(self):
        result = find_quote_in_body("hello", "")
        assert result is None

    def test_quote_with_multiple_spaces_in_body(self):
        body = "the    deal   is   done"
        quote = "the deal is done"
        result = find_quote_in_body(quote, body)
        assert result is not None

    def test_long_whitespace_run(self):
        body = "start" + " " * 50 + "end"
        quote = "start end"
        result = find_quote_in_body(quote, body)
        assert result is not None
        assert result[0] == 0  # starts at 'start'

