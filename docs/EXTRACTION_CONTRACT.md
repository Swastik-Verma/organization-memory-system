# Extraction Contract

This document defines what the extraction pipeline guarantees about its
output, what it explicitly does not guarantee, and how consumers of the
output should handle each case.

---

## What the pipeline guarantees

### 1. Schema compliance

Every item in `extractions_final.jsonl` conforms to the extraction schema.
Fields are typed, required fields are present, and list fields default to
empty lists. Pydantic validation enforces this at extraction time; items
that fail validation are either repaired (via the repair-retry loop) or
excluded.

### 2. Evidence traceability

Every relationship extraction includes an `evidence` field containing text
the LLM claimed to quote from the source email. Every evidence quote has
been checked against the source email body via whitespace-normalized matching:

- `evidence_verified: true` — the quote was found in the source body.
  `char_start` and `char_end` point to the exact location in the original
  (unmodified) body text.
- `evidence_verified: false` — the quote could not be located. Offsets are
  null. The quote may be paraphrased, truncated, or hallucinated.

**Verification rate:** 96.1% (7,533 of 7,836 relationship evidence quotes).

People, organizations, deals, and decisions do not carry evidence quotes
by design — the extraction prompt did not require them for these fields.

### 3. Confidence scoring

Every item has a `confidence` score between 0.05 (floor) and 1.0, computed
deterministically from verifiable signals. The score is accompanied by a
`confidence_penalties` audit trail listing every deduction and its reason.

Scoring is field-aware:
- **Relationships** (evidence-bearing): scored on verification status, quote
  length, noise region overlap, entity completeness
- **Other fields** (no evidence): receive a 0.10 baseline uncertainty penalty,
  plus field-specific checks (missing email address, etc.)

The same input always produces the same score. Scores are never derived from
LLM self-assessment.

### 4. Quality gating

Every item has a `status` field:
- `approved` — confidence ≥ 0.70 and passes all structural checks
- `review` — confidence between 0.30 and 0.70, awaiting human review
- `rejected` — confidence < 0.30 OR fails a structural hard-reject rule

Hard-reject rules (bypass confidence entirely):
- Entity missing a name
- Decision missing a description
- Relationship missing source or target endpoint
- Self-referential relationship (source = target)
- Relationship type outside the closed vocabulary
- Relationship evidence both unverified and under 20 characters
- Relationship with no evidence at all

**Gate results:** 152,255 approved (99.98%), 22 review (0.01%), 6 rejected (0.00%).

### 5. Version tracking

Every extraction is stamped with:
- `prompt_version` — SHA-256 hash (12 chars) of the prompt text
- `model_name` — the model used (e.g. "gemini-3.1-flash-lite")

This enables identification of stale extractions after prompt changes.

### 6. Idempotent enrichment

Running the enrichment pipeline multiple times on the same input produces
identical output. No randomness is involved in verification, scoring, or
gating.

---

## What the pipeline does NOT guarantee

### 1. Factual correctness

Evidence verification confirms a quote exists in the source email. It does
not confirm the LLM interpreted the quote correctly. A verified quote like
"John discussed the deal with Sarah" could be extracted as
`John negotiating_with Sarah` when the actual relationship is `informs`.

Manual evaluation (deferred to Day 49) will measure factual accuracy.

### 2. Completeness

The pipeline does not guarantee that every fact in an email is extracted.
Some facts may be missed entirely — the LLM focused on different content,
the fact was expressed ambiguously, or it fell in a noise region the LLM
was instructed to de-prioritize.

### 3. Evidence for non-relationship fields

People, organizations, deals, and decisions have no evidence quotes. Their
presence in an extraction means the LLM identified them in the email, but
there is no traceable quote to verify. Confidence for these fields reflects
entity completeness signals only.

### 4. Temporal precision

`valid_from` on claims is the date of the email where the fact was first
observed, not the date the fact became true. A relationship that started
in January but was first mentioned in a March email will show
`valid_from = March`. This is "first observed," not "true start date."

### 5. Entity uniqueness

The same real-world person may appear as multiple different name strings
("Steven Kean", "Steven J Kean", "Steve Kean"). The extraction pipeline
does not resolve these — that is the responsibility of Week 3 entity
canonicalization.

---

## How consumers should use this output

### Graph loader (Week 4)

- Load only items where `status == "approved"`
- Skip `review` items (they await human judgment)
- Skip `rejected` items (they are structurally broken or low confidence)
- Use `confidence` to set the initial confidence on graph Claim nodes
- Use `char_start`/`char_end` to create Evidence nodes with correct offsets
- Use `evidence_verified` to set the `in_quoted_block` flag (unverified
  evidence should be visually distinguished in the frontend)

### Chatbot (Week 5)

- Use `confidence` to rank competing evidence for the same question
- Distinguish between verified and unverified evidence in citations
- Never present rejected items in answers

### Frontend (Week 6-7)

- Show confidence as a visual indicator (badge, color, bar)
- Show `confidence_penalties` on hover/click for transparency
- Visually distinguish verified vs unverified evidence quotes
- Highlight evidence text using `char_start`/`char_end` in the source body

---

## Pipeline statistics

| Metric | Value |
|---|---|
| Emails in corpus | 517,389 |
| Extraction subset | 10,000 |
| Total items extracted | 152,283 |
| Evidence verification rate | 96.1% |
| Average confidence | 0.889 |
| Approved | 152,255 (99.98%) |
| Review | 22 (0.01%) |
| Rejected | 6 (0.00%) |
| Prompt version | v2 |
| Model | gemini-3.1-flash-lite |