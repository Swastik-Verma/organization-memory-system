# Ontology Design — Knowledge Graph Schema

## Core decision: reified claims (Model B)

Relationships between entities are stored as **nodes** (`:Claim`), not as
direct edges. A direct edge `(:Person)-[:REPORTS_TO]->(:Person)` is simpler,
but a Neo4j relationship cannot be the endpoint of another relationship — so
there is nowhere to attach:

- Multiple evidence items supporting the same fact
- A validity window (valid_from / valid_to)
- A supersession link to a newer contradicting claim
- A conflict link between two claims that disagree
- A confidence score
- Soft deletion flags

Reifying the claim as a node solves all of these. The cost is one extra hop
per query (Person → Claim → Person instead of Person → Person). The benefit
is that every feature in the plan (temporal queries, conflict detection,
confidence decay, evidence trails) works naturally.

## Node types

| Label | What it represents | ID strategy |
|---|---|---|
| Person | A real human | Slugified canonical name |
| Organization | A company, government body, etc. | Slugified canonical name |
| Deal | A business transaction or contract | Slugified name |
| Decision | An action or choice stated in email | Hash of message_id + description |
| Claim | A reified relationship between entities | Hash of message_id + type + subject + object + quote |
| Evidence | A verbatim quote from an email body | Hash of message_id + quote |
| Message | One email from the corpus | Original RFC 2822 Message-ID |

## Temporal model

- `valid_from` = date of the email that stated the fact (first observed)
- `valid_to` = null (still true) until a later email contradicts it
- This is "first observed at," not true validity — we cannot know when a
  fact actually started being true, only when we first saw evidence for it
- 535 emails have null dates — their claims get `valid_from = null`,
  excluded from point-in-time queries, included in full-history queries

## Org type normalization

The LLM produces 120+ free-text org_type values. These are normalized at
ingestion to a closed set: company, government, nonprofit, university,
internal_division, other.

## The affects problem (§9.1)

`Decision.affects` contains a mix of real names ("Cindy Olson") and
generic placeholders ("employees", "the team"). 91.3% match a known
person or org name — these become real AFFECTS edges. The remaining 8.7%
are stored as `affects_unresolved` text on the Decision node. No node is
created for unresolvable strings, preventing fake hub nodes from
corrupting graph metrics.

## Alternatives rejected

- **Direct edges instead of reified claims**: rejected because evidence,
  temporal windows, and supersession links cannot attach to Neo4j edges
- **Random UUIDs for node IDs**: rejected because MERGE becomes useless —
  re-running ingestion creates duplicates instead of being idempotent
- **LLM-reported confidence scores**: rejected because the model returns
  ~0.9 for everything regardless of actual certainty. Confidence will be
  computed deterministically from verifiable signals at ingestion (Days 8-11)


## Chunking

Not implemented. Body length analysis of the 10k subset confirmed:
- P99 = 12,229 chars (~3,057 tokens)
- Max = 136,752 chars (~34,188 tokens) — only 2 emails
- Gemini flash-lite context window exceeds 100k tokens

All 10k emails were successfully extracted without chunking. Even the
longest email (34k tokens) fits well within the model's context window.
If the project scaled to a corpus with longer documents (e.g. full
reports or legal filings), chunking would be needed — the thread
reconstructor output provides the metadata (thread membership,
chronological position) that a chunker would need.

## Ingestion layer guarantees

The ingestion layer (parsing → noise detection → thread reconstruction)
makes these guarantees about its output:

### ParsedEmail
1. Every email has a non-empty `message_id`, `from_addr`, and `body`
2. Dates are either valid datetimes within 1995-2005 or null — never
   garbage values from clock errors
3. All 517,389 parseable emails are captured; the 12 `kitchen-l` failures
   are documented and accepted (0.002%)
4. No duplicate `message_id` values exist in the parsed output

### Noise detection
5. Forwarding headers (`-----Original Message-----`) are detected with
   character offsets
6. Quoted reply blocks (`> ` lines and `wrote:` patterns) are detected
7. Signatures are detected only in the bottom half of emails to avoid
   false positives on section dividers
8. The raw body is never modified — noise regions are annotations only
9. `is_in_noise(start, end, regions)` returns true if any overlap exists

### Thread reconstruction
10. Threads are built from normalized subject lines (Re:/Fw:/Fwd: stripped)
11. Emails with empty subjects are placed in standalone single-message threads
12. Each thread is chronologically sorted by date
13. This is approximate — unrelated emails sharing a subject will be
    wrongly grouped. Header-based threading (In-Reply-To/References)
    would be more precise but these headers are absent from this corpus

### What is NOT guaranteed
- Noise detection does not catch unmarked quoted text (pasted without
  `>` markers or forwarding headers)
- Thread grouping may merge unrelated conversations with identical subjects
- The 535 null-date emails are included but excluded from date-sorted views


## Evidence Verification

Every evidence quote extracted by the LLM is verified against the source email body
before it enters the graph. Verification uses whitespace-normalized matching — all
whitespace (newlines, tabs, multiple spaces) is collapsed to single spaces before
comparison, because the Enron email bodies are hard-wrapped at ~76 characters and
the LLM returns quotes without the artificial line breaks.

Quotes that pass verification receive character offsets (`char_start`, `char_end`)
pointing into the original (unmodified) email body. These offsets enable the frontend
evidence panel to highlight the exact source text.

Quotes that fail verification are flagged `evidence_verified: false` with null offsets.
They are not deleted — the extraction is preserved as-is — but they receive a confidence
penalty during scoring (Day 9) and are visually distinguished in the frontend.

### Verification rate

On the 10,000-email extraction subset: **96.1%** (7,533 of 7,836 total evidence quotes
verified). The 3.9% unverified quotes are primarily cases where the LLM paraphrased
slightly rather than quoting verbatim.

### What verification does NOT do

- It does not attempt fuzzy or approximate matching. A near-miss is still flagged as
  unverified. This is deliberate — the verification rate is meant to honestly measure
  extraction quality, not to be maximized.
- It does not modify the extracted data. Raw extractions are immutable; verification
  adds metadata alongside them.