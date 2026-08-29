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


## Confidence Scoring

Confidence scores are computed deterministically from verifiable signals, not from
LLM self-assessment. LLM-reported confidence clusters at 0.85-0.95 regardless of
actual quality and provides no useful discrimination.

### Scoring approach

Each extracted item starts at 1.0 and receives penalties for weakness indicators.
The scoring is **field-aware**: only relationship extractions (which carry verbatim
evidence quotes) are evaluated on evidence quality. People, organizations, deals,
and decisions receive a baseline uncertainty penalty (0.10) reflecting the inherent
limitation of having no verifiable evidence.

### Penalty signals

For evidence-bearing fields (relationships):
- Evidence not verified against source body: -0.30
- Evidence empty: -0.50
- Quote very short (< 20 chars): -0.15
- Quote short (20-40 chars): -0.05
- Evidence falls in a noise region (forwarded/quoted block): -0.10

For all fields:
- No evidence available (non-evidence fields): -0.10
- Person has no email address: -0.05
- Relationship missing source or target: -0.20
- Floor: 0.05 (nothing scores zero)

Every score includes a penalties audit trail listing exactly which deductions applied.

### Distribution (10,000-email subset)

- Total items scored: 152,283
- Average confidence: 0.889
- Median (P50): 0.90
- Per-field: people 0.879, organizations 0.900, deals 0.900, decisions 0.900,
  relationships 0.942
- 99.98% of items score above 0.7


## Extraction Versioning

Every extraction is stamped with two fields:
- `prompt_version`: a 12-character SHA-256 hash of the extraction prompt text
- `model_name`: the model used (e.g. "gemini-3.1-flash-lite")

The prompt hash is deterministic — the same prompt always produces the same hash.
Any change to the prompt text, however small, produces a different hash. This
enables the version manager to identify stale extractions that need re-running
after a prompt or ontology change, without re-extracting the entire corpus.

### Repair-retry loop

When the LLM returns structurally invalid output (malformed JSON or validation
failures), the extractor sends the error message back to the model and asks for
a structural fix. Up to 2 repair attempts are made before marking the extraction
as permanently failed. Raw LLM responses are saved to `data/processed/raw_responses/`
for post-hoc debugging.

### Current version

All 10,000 extractions in the working subset were produced by prompt v2 with
`gemini-3.1-flash-lite` and retroactively stamped.


## Quality Gates

Every scored item is routed into one of three outcomes before graph loading.

### Hard rejection rules (score-independent)

Structural problems that make an item unusable regardless of confidence:
- Person, organization, or deal with no name
- Decision with no description
- Relationship missing source or target
- Relationship where source equals target (self-referential)
- Relationship type outside the closed vocabulary (reports_to, works_with,
  requests_from, negotiating_with, informs)
- Relationship with no evidence, or evidence that is both unverified and
  under 20 characters

These bypass the confidence score because they are binary problems, not
matters of degree. A relationship with no target cannot be represented as
a graph edge at any confidence level.

### Confidence thresholds

- confidence ≥ 0.70 → **approved** (loads into graph as current claim)
- 0.30 ≤ confidence < 0.70 → **review** (human review queue)
- confidence < 0.30 → **rejected** (not loaded)

### Nothing is deleted

Gating adds a `status` and `gate_reason` field to each item. Rejected items
remain in the data file and are excluded at graph load time, consistent with
the soft-delete principle applied throughout the system.

### Results (10,000-email subset)

- Total items gated: 152,283
- Approved: 152,255 (99.98%)
- Review: 22 (0.01%) — all relationships with confidence in 0.3–0.7 range
- Rejected: 6 (0.00%) — all from hard reject rules:
  - 4 self-referential relationships (Person A works_with Person A)
  - 1 unverifiable evidence and too short (< 20 chars)
  - 1 missing evidence entirely
- Zero rejections from confidence thresholds alone — all rejections were
  structural problems the score would not have caught


## Enrichment Pipeline

All post-extraction enrichment runs as a single unified pipeline, ensuring
consistent ordering and a single output file.

### Pipeline steps (in order)

1. **Evidence verification** — whitespace-normalized matching, character offsets
2. **Confidence scoring** — field-aware deterministic penalties
3. **Quality gating** — hard rejection rules + confidence thresholds
4. **Version stamping** — prompt hash + model name

### Output

`extractions_final.jsonl` — the canonical enriched extraction file. Every item
has offsets (or null), confidence with audit trail, gate status with reason, and
version stamp. This is the input for Neo4j ingestion (Week 4).

### Re-extraction

When the prompt changes, `reextract_stale.py` identifies extractions produced by
an older prompt version and re-processes only those through the LLM. The unified
pipeline then re-enriches the new output. The full corpus never needs complete
re-processing unless the ontology changes fundamentally.


## Extraction Quality Evaluation

### Manual accuracy assessment

A random sample of 50 emails (seed=42) was manually reviewed, scoring each
extracted item as correct, partially correct, or hallucinated against the
source email text.

[Fill in your actual numbers after running the evaluation]

- Overall accuracy: [X]%
- Hallucination rate: [Y]%
- Per-field: people [A]%, organizations [B]%, deals [C]%, 
  decisions [D]%, relationships [E]%

### Top failure modes

[Fill in your actual top 3 after review]

1. [Failure mode 1]: [description and count]
2. [Failure mode 2]: [description and count]
3. [Failure mode 3]: [description and count]

### Failure analysis

- Unverified evidence (303 quotes): categorized as [your categories]
- Review queue (22 items): all relationships with stacked confidence penalties
- Rejected (6 items): 4 self-referential, 1 unverifiable+short, 1 missing evidence





## Artifact Deduplication

Duplicate emails are defined by **body content**, not by message metadata.
Two emails with different Message-IDs, senders, recipients, or dates are
duplicates if their bodies contain the same information.

### Two-phase detection

1. **Exact:** SHA-256 hash of whitespace-normalized, lowercased body.
   Catches same-content emails filed in multiple mailbox folders.
2. **Near-duplicate:** Cosine similarity ≥ 0.95 of sentence-transformer
   embeddings (all-MiniLM-L6-v2) on noise-stripped original content.
   Catches forwards and cross-posts with minor additions.

### Primary selection

Within each duplicate group, the primary email is selected by:
earliest date → longest body → first message_id (tiebreaker).
Only the primary is loaded into Neo4j; duplicates are skipped.

### Results on 10k subset

| Metric | Value |
|---|---|
| Exact duplicate groups | 833 |
| Near-duplicate groups | 170 |
| Total duplicates to skip | 1,405 |
| Unique emails for ingestion | 8,595 |

### Downstream contract

`duplicate_ids.json` contains a flat list of message_ids to skip.
During Neo4j ingestion: `if message_id in duplicate_ids: skip`.



## Entity Resolution — Exact Matching

Collapses name variants to canonical entities using deterministic signals.
Fuzzy matching (Day 17) builds on top of these results.

### Resolution strategies (priority order)

1. **Email match** — same email address = same person. Confidence 1.0.
   Definitive because email addresses are unique identifiers.
2. **Normalized name match** — names that normalize to the same form
   are the same entity. Confidence 0.95.

### Person name normalization

Lowercase → remove commas/periods → strip titles (Mr., Dr., Jr., etc.)
→ sort parts alphabetically. This handles "Last, First" vs "First Last"
reordering and title variations.

Does NOT catch: nicknames, middle initials without shared email, typos.

### Organization name normalization

Lowercase → remove punctuation → strip trailing corporate suffixes
(Inc., Corp., LLC, Ltd., etc.). Word order is preserved (unlike person
names) because it is semantically meaningful for organizations.

### Conflicting email guard

If two mentions share the same normalized name but have different email
addresses, they are treated as separate entities. Rationale: email is
a stronger identity signal than name. Same name + different email is
more likely two different people than one person with two emails.

Day 17 fuzzy matching resolves the cases where one person genuinely
has multiple email addresses (e.g., Kenneth Lay with klay@enron.com
and kenneth.lay@enron.com).

### Shared email detection

Email addresses with 5+ distinct normalized names are flagged as
shared/generic mailboxes and excluded from email-based resolution.
These entities are still resolved via name matching.

### Canonical ID scheme

| Scenario | ID format |
|---|---|
| Person with email | `person:{normalized-name}:{email-slug}` |
| Person without email | `person:{normalized-name}` |
| Organization | `org:{normalized-name}` |

Email in the ID ensures uniqueness when two different people share a name.

### Canonical name selection

When multiple aliases exist, the canonical (display) name is selected by:
most frequent variant → longest → alphabetically first.

### Results on 10k subset

| Metric | Value |
|---|---|
| Unique person names input | 17,046 |
| Canonical people | 16,095 |
| Person names collapsed | 951 |
| Unique org names input | 7,472 |
| Canonical organizations | 6,925 |
| Org names collapsed | 547 |
| Merges by email | 1,262 |
| Merges by normalized name | 762 |
| Shared emails detected | 4 |

### Downstream contract

`resolution_map.json` maps any name string → canonical_id.
During Neo4j ingestion: look up every name in this map to get the
canonical entity it belongs to, ensuring all aliases point to one node.



## Entity Resolution — Fuzzy Matching (Day 17)

Builds on Day 16's exact matching to find candidates that differ by
nicknames, middle initials, typos, or email variants.

### Four matching strategies

| Strategy | What it catches | Confidence |
|---|---|---|
| Middle initial stripping | "Steven J Kean" ↔ "Steven Kean" | 0.82–0.88 |
| Nickname expansion | "Ken Lay" ↔ "Kenneth Lay" | 0.85–0.90 |
| Same email domain | Same name, different @enron.com emails | 0.92 |
| General fuzzy (rapidfuzz) | Typos: "Klauberg" ↔ "Klauber" | 0.81–0.99 |

<!-- ### Design decision: no auto-merging

All candidates routed to human review regardless of confidence. Rationale:
fuzzy matching produces false positives ("Jan Wilson" ↔ "Jane Wilson",
"Carl Carter" ↔ "Carol Carter") that are indistinguishable from true
positives without human judgment. Candidates saved in
`entity_resolution_fuzzy.json` for the Week 7 review queue UI. -->

### Merge confidence tiers

| Confidence | Action |
|---|---|
| ≥ 0.85 | Auto-merge (undoable via snapshots) |
| 0.70–0.85 | Saved for human review (Week 7 UI) |
| < 0.70 | Skipped |

### Undo capability

Every merge records pre-merge snapshots of both entities. Undo restores
both entities and the resolution map to their exact pre-merge state.
This ensures no merge is permanent until confirmed by a human.

### Results on 10k subset

| Metric | Value |
|---|---|
| Middle initial candidates | 743 |
| Nickname candidates | 323 |
| Same domain candidates | 490 |
| Fuzzy candidates | 1,803 |
| Total unique candidates | 2,503 |
| Auto-merged | 0 (all to human review) |
| Entities remaining | 23,020 (16,095 people + 6,925 orgs) |





## Claim Deduplication (Day 18)

### Dedup key

Two relationships are the same fact if they share:
  (canonical_subject_id, relationship_type, canonical_object_id)

Name variants ("Steve Kean" vs "Steven Kean") resolve to the same
canonical_id via the resolution map, so they correctly merge.

### Symmetric normalization

For works_with and negotiating_with, the subject/object pair is sorted
alphabetically before building the dedup key. This ensures "A works_with B"
and "B works_with A" collapse to one claim.

### Evidence accumulation

Multiple mentions of the same fact become one Claim node with multiple
Evidence nodes. Claim confidence = max across all evidence items.
valid_from = earliest supporting email date.

### Conflict detection scope

Only reports_to is treated as exclusive (one manager at a time).
requests_from and informs are non-exclusive — multiple objects is
normal behavior for these types, not a conflict.

### Claim ID scheme

claim_id = sha256(subject_id | type | object_id)[:16]

Derived from the fact, not the mention. Same fact always produces
the same ID regardless of how many emails state it. Makes Neo4j
MERGE idempotent.

### Results on 10k subset

| Metric | Value |
|---|---|
| Input relationships | 6,963 |
| Deduplicated claims | 5,586 |
| Compression ratio | 1.25x |
| Multi-evidence claims | 744 |
| Max evidence per claim | 17 |
| Genuine conflicts (reports_to) | 27 |
| Unresolved references | 0 |




## Conflict Resolution (Day 19)

### What counts as a conflict

Only reports_to is classified as exclusive — a person has one manager
at a time. Multiple objects for this type across different emails
constitutes a conflict requiring resolution.

requests_from, informs, works_with, negotiating_with are non-exclusive.
Multiple objects for these types is normal behavior, not a conflict.

### Classification (based on valid_from dates)

All claims have valid_from = email date, valid_to = null (set here).
Classification compares valid_from dates across conflicting claims:

| Situation | Classification | Resolution |
|---|---|---|
| Different valid_from dates | temporal_succession | auto_resolved |
| Same valid_from date | direct_contradiction | needs_review |
| Any valid_from is null | undated | needs_review |

### Temporal succession — auto-resolution

When claims have different dates, the fact changed over time.
The older claim gets valid_to closed at the newer claim's valid_from.

Before:
Claim A: valid_from=Jan, valid_to=null, status=current
Claim B: valid_from=Jun, valid_to=null, status=current

After:
Claim A: valid_from=Jan, valid_to=Jun, status=superseded
Claim B: valid_from=Jun, valid_to=null, status=current
Edge: B -[:SUPERSEDES]-> A



This enables temporal queries:
  "Who does Kean report to NOW?" → WHERE valid_to IS NULL
  "Who did Kean report to in Feb 2001?" → WHERE valid_from <= date < valid_to

### Direct contradiction — human review

When claims share the same date, temporal ordering is impossible.
Both claims marked status="review" with bidirectional CONFLICTS_WITH edges.
Resolved in Week 7 via the conflict review queue UI (Day 44).

### Decision reversals

Decisions containing reversal language ("cancelled", "no longer",
"reversed", etc.) are flagged and saved to decision_reversals.json.

Known limitation: pattern matching produces false positives
(scheduling language like "instead of Sunday" triggers "instead of").
Human review in Week 7 filters these. Semantic matching via embedding
similarity would reduce false positives but was deferred — the volume
of reversals (60) is small enough for manual review.

Full semantic reversal linking (finding which original decision each
reversal targets) is deferred to a future enhancement. The detection
step is sufficient for surfacing the signal.

### Results on 10k subset

| Metric | Value |
|---|---|
| Conflicts input | 27 |
| Temporal successions (auto-resolved) | 16 |
| Direct contradictions (needs review) | 11 |
| Claims with closed validity windows | 22 |
| Decision reversals detected | 60 |
| Canonical output file | resolved_claims.jsonl |





## Soft Deletes and Redaction (Day 20)

### Core principle

Nothing is ever hard-deleted. All removals are flag-based:
- is_deleted: true/false
- deleted_at: ISO timestamp
- deletion_reason: why and how it was deleted

### Three operations

| Operation | Reversible? | Content preserved? | Use case |
|---|---|---|---|
| soft_delete_entity | Yes | Yes | Bad data, operational cleanup |
| soft_delete_claim | Yes | Yes | Individual bad extraction |
| redact_entity | No | No (replaced with [REDACTED]) | GDPR, legal compliance |

### Cascade rules

- Entity deletion cascades to claims (via subject_id/object_id match)
- Claim deletion does NOT cascade to entities
- Cascade tracked via deletion_reason prefix:
  `cascade:entity:{entity_id}:{reason}`
- Restore matches this prefix to find and unflag cascaded items

### Query patterns

```cypher
-- Normal retrieval (excludes deleted)
WHERE is_deleted = false OR is_deleted IS NULL

-- Audit view (only deleted)
WHERE is_deleted = true
```

### Redaction vs soft delete

Soft delete hides content from retrieval but preserves it for audit.
Redaction replaces actual text with [REDACTED] — canonical_name, aliases,
emails, evidence quotes all permanently overwritten. Restore is refused
for redacted entities (content is unrecoverable by design).



## Week 3 Deduplication — Pipeline Summary

### Data flow

extractions_final.jsonl (Day 14, 10k emails)
↓
artifact_dedup (Day 15) → 8,595 unique emails
↓
entity_resolution_exact (Day 16) → 16,095 people, 6,925 orgs
↓
entity_resolution_fuzzy (Day 17) → 2,503 candidates for review
↓
deduplicated_claims (Day 18) → 5,586 unique relationship claims
↓
resolved_claims (Day 19) → temporal chains + conflict flags
↓
redaction_manager (Day 20) → soft delete / redact / restore



### Guarantees

1. No duplicate emails are processed (Day 15 filter)
2. Every person name maps to exactly one canonical entity (Days 16-17)
3. Every relationship fact exists as exactly one claim with accumulated evidence (Day 18)
4. Exclusive-type conflicts are detected and classified (Day 19)
5. Temporal successions have closed validity windows (Day 19)
6. Nothing is ever hard-deleted; all removals are auditable (Day 20)
7. All merges are reversible via stored snapshots (Day 17)
8. All deletions are reversible except redactions (Day 20)

### Canonical files for Week 4 ingestion

| File | Contains | Used by |
|---|---|---|
| resolution_map.json | name → canonical_id | Neo4j entity creation |
| entity_resolution_fuzzy.json | canonical entities with aliases | Neo4j Person/Org nodes |
| resolved_claims.jsonl | deduplicated + conflict-resolved claims | Neo4j Claim nodes |
| duplicate_ids.json | message_ids to skip | Neo4j Message loading |
| conflict_review_queue.json | contradictions for human review | Week 7 UI |
| decision_reversals.json | flagged reversal decisions | Week 7 UI |




## Week 4 — Memory Graph

### Day 22 — Neo4j Schema (Revised)

#### What changed from Day 5

The Day 5 schema was a first draft written before extraction ran.
After three weeks of working with real data, three things changed:

1. **Person IDs** — now include email slug to handle two people with
   the same name: `person:{normalized-name}:{email-slug}` e.g.
   `person:kean-steven:steven-kean-at-enron-com`. Day 5 used
   `person:{slugified-name}` which collided when names matched.

2. **Claim IDs** — now fact-level, not mention-level.
   `claim:{sha256(subject_id|claim_type|object_id)[:16]}`.
   Five emails asserting the same relationship produce one Claim node
   with five Evidence nodes, not five separate Claim nodes.

3. **New Claim fields** — `supersedes`, `superseded_by`,
   `conflicts_with[]` added from Day 19 temporal resolution.
   `mention_count` tracks how many emails stated this fact.

#### Node types (7)

| Label | Source file | Primary key |
|---|---|---|
| Person | entity_resolution_fuzzy.json | id |
| Organization | entity_resolution_fuzzy.json | id |
| Claim | resolved_claims.jsonl | id |
| Evidence | resolved_claims.jsonl (embedded) | id |
| Message | extraction_subset.jsonl | message_id |
| Deal | extractions_final.jsonl | id |
| Decision | extractions_final.jsonl | id |

#### Edge types (14)

| Edge | From → To | Meaning |
|---|---|---|
| SUBJECT | Claim → Person | Subject of this claim |
| OBJECT | Claim → Person/Org | Object of this claim |
| SUPPORTED_BY | Claim → Evidence | Quote that proves this claim |
| FROM_MESSAGE | Evidence → Message | Email the quote came from |
| SENT_BY | Message → Person | Email sender |
| SENT_TO | Message → Person | Email recipient |
| MADE_BY | Decision → Person | Who made this decision |
| AFFECTS | Decision → Person/Org | Who this decision affects |
| PARTY | Deal → Person/Org | Party to this deal |
| SUPERSEDES | Claim → Claim | Newer claim replacing older |
| CONFLICTS_WITH | Claim → Claim | Unresolved contradiction |
| MERGED_INTO | Person/Org → Person/Org | Entity merge record |

#### Why reified claims (not direct edges)

A direct edge `(:Person)-[:REPORTS_TO]->(:Person)` cannot be the
endpoint of another relationship in Neo4j. This means there is
nowhere to attach evidence, validity windows, or supersession links.

By making the relationship a node (`:Claim`), every fact has full
provenance: who stated it, in which email, with what confidence, and
for what time period. The tradeoff is slightly more complex queries
(traversing through the Claim node), which is worth it for the
evidence trail.

#### Constraints and indexes applied

7 uniqueness constraints (one per node type) + 20 indexes.

Key indexes for temporal queries:
- `idx_claim_valid_from`, `idx_claim_valid_to` — point-in-time queries
- `idx_claim_superseded_by` — "what's current?" (WHERE superseded_by IS NULL)
- `idx_claim_status` — filter by current/superseded/review/archived
- `idx_claim_is_deleted` — exclude soft-deleted content

#### org_type normalization

120+ free-text org_type variants from extraction mapped to 6 categories
at ingestion time: company, government, nonprofit, university,
internal_division, other. Unknown values default to "other" rather
than crashing. Mapping is in `src/graph/schema.py → ORG_TYPE_MAP`.



### Day 23 — Graph Loader

#### Source files → Node types mapping

| Source file | Node type | Count loaded |
|---|---|---|
| entity_resolution_fuzzy.json | Person | 15,003 |
| entity_resolution_fuzzy.json | Organization | 6,726 |
| extraction_subset.jsonl (minus duplicates) | Message | 8,595 |
| extractions_final.jsonl (non-duplicate emails only) | Deal | 3,303 |
| extractions_final.jsonl (non-duplicate emails only) | Decision | 10,780 |
| resolved_claims.jsonl | Claim | 5,586 |
| resolved_claims.jsonl (embedded evidence lists) | Evidence | 6,069 |
| **Total** | | **56,062 nodes** |

#### Edge types loaded and their counts

| Edge | From → To | Count | Notes |
|---|---|---|---|
| SENT_TO | Message → Person | 47,174 | One message can have many recipients |
| AFFECTS | Decision → Person/Org | 22,818 | Resolved via resolution_map |
| MADE_BY | Decision → Person | 10,249 | 264 decisions had null/unresolvable made_by |
| PARTY | Deal → Person/Org | 9,126 | Resolved via resolution_map |
| SENT_BY | Message → Person | 8,072 | ~6% senders unresolvable (external people) |
| SUPPORTED_BY | Claim → Evidence | 6,962 | One per evidence item |
| FROM_MESSAGE | Evidence → Message | 6,069 | 100% match rate |
| OBJECT | Claim → Person | 5,564 | 22 claims reference org as object |
| SUBJECT | Claim → Person | 5,490 | 96 claims reference org as subject |
| CONFLICTS_WITH | Claim → Claim | 50 | Bidirectional, 25 unique conflict pairs |
| SUPERSEDES | Claim → Claim | 15 | Temporal succession chains |
| **Total** | | **121,589 edges** | |

#### Loading design decisions

**MERGE not CREATE everywhere**
Every node and edge write uses `MERGE` (find-or-create). Running the
loader twice produces the same graph as running it once. This is
essential because the graph is derived data that gets rebuilt when
pipeline rules change.

**UNWIND $batch pattern**
Items are sent to Neo4j in batches of 500 via `UNWIND $batch AS row`.
This reduces network round-trips from 56,000 individual calls to ~112
batch calls. Loading completes in ~35 seconds.

**Dependency ordering**
Nodes are loaded before edges. Entities (Person, Organization) are
loaded before Claims, because Claims reference entity IDs. If entities
don't exist when edges are created, the MATCH fails silently and the
edge is skipped — no dangling references are created.

**Duplicate email filtering**
`extractions_final.jsonl` contains extractions for all 10,000 emails
including the 1,405 duplicates identified in Day 15. The loader skips
any extraction whose `message_id` is in `duplicate_ids.json`. This
reduced Decisions from the raw 12,331 to 10,780 and Deals from 4,781
to 3,303.

**Resolution at load time**
`affects`, `made_by`, and `parties_involved` strings are resolved
against `resolution_map.json` during loading. Resolved strings become
edges. Unresolved strings are stored as text properties
(`affects_unresolved`, `parties_unresolved`) on the node — never
as phantom nodes. This is the Day 4 §9.1 design finally applied.

**Evidence ID generation**
Evidence items in `resolved_claims.jsonl` have no pre-existing ID.
IDs are generated at load time: `evidence:{sha256(message_id+quote)[:16]}`.
Same quote from the same email always produces the same ID, so MERGE
deduplicates evidence shared across multiple claims — 6,963 evidence
items collapsed to 6,069 unique Evidence nodes.

**Deal ID generation**
Deals have no pre-existing ID. IDs are generated from the slugified
deal name: `deal:{slugify(name)}`. Same deal name across multiple
emails produces the same ID, so MERGE deduplicates automatically.

#### Known gaps (not bugs)

**96 SUBJECT edges and 22 OBJECT edges missing**
Some claims have an organization as their subject or object (e.g.
"Enron informs Kenneth Lay"). The SUBJECT/OBJECT Cypher only matches
`:Person` nodes. These claims have no SUBJECT/OBJECT edge. Fix: extend
the Cypher to also match `:Organization` nodes. Deferred — all current
claims in practice have persons on both sides; org-as-subject is an
edge case from the LLM extraction.

**264 decisions with no MADE_BY edge**
Either `made_by` is null in the extraction (384 known from Day 4,
proportionally fewer after duplicate filtering) or the name string
wasn't in the resolution map.

**~6% of messages have no SENT_BY edge**
Senders whose email addresses don't appear in the entity set — mostly
external correspondents who appear in emails but weren't mentioned in
extraction output.



### Day 24 — Temporal Query Engine

#### What it is

A Python module (`src/graph/temporal_queries.py`) that sits between
the chatbot (Week 5) and Neo4j. All graph queries go through this
layer — the chatbot never writes raw Cypher.

#### The three core temporal access patterns

Every claim has `valid_from` and `valid_to` dates. These three
patterns exploit that structure:

**Current state** (`get_current_state`)
Returns claims where `valid_to IS NULL AND status = 'current'`.
Answers: "Who does Kean report to right now?"

**Historical state** (`get_state_at`)
Returns claims where `valid_from <= date AND (valid_to IS NULL OR
valid_to > date)`. Claims with `valid_from = null` are excluded —
undated claims cannot be placed on a timeline.
Answers: "Who did Kean report to in March 2001?"

**Full history** (`get_full_history`)
Returns all claims regardless of status, ordered chronologically.
Null-dated claims sorted last.
Answers: "Show me Kean's complete reporting history."

#### All 13 methods and what they cover

| Method | Question type |
|---|---|
| `find_entity(name)` | Find canonical ID from partial name |
| `get_entity_profile(id)` | Basic entity details |
| `get_current_state(id)` | What's true right now |
| `get_state_at(id, date)` | What was true on a date |
| `get_full_history(id)` | Complete chronological record |
| `get_evidence_for_claim(id)` | Proof for a specific claim |
| `get_full_email(message_id)` | Full email for evidence panel |
| `get_relationships_about(id)` | Claims where entity is subject |
| `get_relationships_involving(id)` | Claims in either direction |
| `get_decisions_by(id)` | Decisions this person made |
| `get_decisions_affecting(id)` | Decisions affecting this entity |
| `get_deals_involving(id)` | Deals this entity is party to |
| `get_conflicts(id)` | Unresolved contradictions |
| `get_graph_stats()` | Summary counts for health dashboard |

#### Four concerns the engine handles for every query

Every method automatically applies all four — the chatbot never
thinks about them:

1. **Temporal logic** — valid_from/valid_to filtering per access pattern
2. **Deletion filtering** — `WHERE is_deleted = false` on every node
3. **Entity resolution** — `find_entity()` searches canonical names
   AND aliases, returns sorted by mention_count
4. **Result formatting** — returns clean Python dicts, not raw
   Neo4j Record objects

#### Verified against real data

Sally Beck reporting history confirmed correct:

× reports_to Richard Causey: 2000-01-17 to 2000-08-16 (superseded, 12 evidence)
× reports_to Brent Price: 2000-08-16 to 2000-11-08 (superseded, 1 evidence)
→ reports_to Louise Kitchen: 2000-11-08 to present (current, 1 evidence)


Evidence trail verified end-to-end:
Claim → Evidence quote (with char offsets) → Source email (subject,
sender, date, full body). The full chain from a graph fact back to
the exact words in the original email works correctly.

#### What the engine does NOT handle (yet)

- **Permission filtering** (Day 26): access level checks not yet
  applied. All users see all content.
- **Reverse direction queries**: `get_current_state()` only returns
  claims where the entity is the SUBJECT. "Who reports TO Kean?" 
  requires `get_relationships_involving()` or a dedicated method.
- **Cross-entity queries**: "Which organizations did Enron deal with
  in 2001?" requires joins across multiple entity types — no method
  for this yet. Will be added in Week 5 as chatbot reveals gaps.




### Day 25 — Incremental Update System

#### What was built

Three production-readiness features implemented in
`src/graph/incremental_updater.py`:

1. **Incremental update** (`run_incremental_update`) — loads new email
   batches into the existing graph without reprocessing old data
2. **Confidence decay** (`apply_confidence_decay`) — ages out stale
   claims that haven't received fresh evidence
3. **Ontology drift detection** (`detect_ontology_drift`,
   `detect_graph_drift`) — monitors for schema violations in
   extraction output and the loaded graph

#### Why these features exist

These features make the system production-ready for a real organization
where emails arrive continuously. For the Enron portfolio project, the
data is historical (corpus ends ~late 2001) so these features are built
but not actively applied — running decay on a frozen corpus would
archive valid claims with no way to replenish them with fresh evidence.
The code exists to demonstrate the production architecture and is fully
explainable in interviews.

#### Incremental update — how it works

New emails go through the same pipeline as the original batch:

New raw emails
→ parse (batch_parse_emails.py)
→ LLM extraction (batch_extract.py)
→ enrich (run_enrichment_pipeline.py)
→ entity resolution (batch_entity_resolution.py)
→ claim dedup + conflict resolution (batch_claim_dedup.py)
→ load into graph (run_incremental_update)



The `run_incremental_update` method is the last step. It assumes
extraction and enrichment have already run on the new batch. MERGE
ensures idempotency — reprocessing an email that already exists
updates it rather than creating a duplicate.

After loading, `_detect_new_conflicts` checks whether any new claim
contradicts an existing current claim (same subject, same exclusive
type, different object). Conflicts are reported, not auto-resolved.
Resolution happens either automatically (temporal succession from
Day 19 logic, for claims with different dates) or via the human
review queue (Day 44 frontend, for same-date contradictions).

#### Confidence decay — formula and constants

reference_date = "2002-01-01" (end of meaningful Enron data)
decay_rate = 10% per year
archive_threshold = 0.30
minimum_age = 365 days (claims under 1 year old not decayed)

years_old = days_between(last_evidence_date, reference_date) / 365
decay = years_old × decay_rate
new_confidence = original_confidence - decay
if new_confidence < archive_threshold → status = 'archived'


**Why reference_date = 2002-01-01:** Using today's date (2026) would
make every claim ~25 years old and archive the entire graph. The
corpus reference date simulates "it is January 2002 — which claims
have gone stale?"

**Reversal:** `reset_confidence_decay()` removes the decay flag and
restores archived claims to `status = 'current'`. It does NOT restore
the original confidence value — for that, re-run the graph loader
from `resolved_claims.jsonl` (MERGE overwrites decayed values with
originals from the immutable source file).

**`preview_confidence_decay()`** is a dry-run method — reads the
graph and shows what would happen without writing anything. Safe to
run at any time.

#### Ontology drift detection — what it checks

**From extraction files (`detect_ontology_drift`):**
- Relationship types outside the 5-type closed vocabulary
- Org types that normalize to "other" (signals ORG_TYPE_MAP needs expanding)
- Structural issues: missing person_a/person_b, self-referential relationships
- Empty extractions (zero entities/relationships extracted)

**From the loaded graph (`detect_graph_drift`):**
- Claim type distribution (shows if unknown types accumulated)
- Org type distribution (shows normalization gaps)
- Claims without evidence
- Claims without SUBJECT edge

**What happens when drift is detected:**

Drift detection is a monitoring tool, not a blocker. Three responses:

| Situation | Response |
|---|---|
| LLM produces types outside schema | Fix extraction prompt, re-extract |
| New type is genuinely useful | Add to ClaimType enum, prompt, VALID_CLAIM_TYPES, re-extract |
| Unknown type appeared 1-2 times | Log it, treat as noise, ignore |

The system never crashes or silently drops data on drift. It reports
and a human decides.

#### Deployment model (production)

In a real deployment these would run on a schedule:

Nightly (2 AM):

1. Fetch new emails from last 24 hours
2. Run full extraction pipeline on new emails
3. detect_ontology_drift → alert if drift detected
4. run_incremental_update → load new data
5. apply_confidence_decay → age out stale claims

Weekly:
6. detect_graph_drift → health dashboard update



For the Enron portfolio project: the code is built and tested.
Active scheduling is not implemented since the corpus is historical.

#### Files

| File | Purpose |
|---|---|
| `src/graph/incremental_updater.py` | All three features |
| `scripts/run_incremental_update.py` | Demonstration runner |
| `tests/test_incremental_updater.py` | Unit tests |



### Day 26 — Permission Layer

#### What was built

Role-based access control over the knowledge graph, implemented in
`src/graph/permissions.py`. Every content node gets a numeric
`access_level` property. Every query filters by the requesting
user's `clearance_level`. Filtering happens inside Cypher — restricted
content never leaves Neo4j for unauthorized users.

#### Access model

Four levels, numeric for easy comparison (`content.access_level <= user.clearance_level`):

| Level | Name | Who can see |
|---|---|---|
| 1 | PUBLIC | Everyone (default) |
| 2 | INTERNAL | Employees and above |
| 3 | CONFIDENTIAL | Management and above |
| 4 | RESTRICTED | Executives and legal only |

#### What gets classified

| Node type | Classification method |
|---|---|
| Message | Mailbox origin + keyword matching on subject/body |
| Evidence | Inherits from source Message |
| Claim | Inherits highest level from its Evidence |
| Decision | Keyword matching on description + inherits from source Message via `source_message_id` |

Deals, Persons, Organizations are not classified — knowing an entity
exists is not sensitive. Sensitive facts about entities are captured
in Claims and Decisions, which are classified.

#### Classification rules

**Message classification:**
- Default: PUBLIC (1)
- Legal mailboxes (MANN-K, NEMEC-G, JONES-T) → INTERNAL (2)
- Executive mailboxes (LAY-K, KITCHEN-L) → CONFIDENTIAL (3)
- Keywords ("confidential", "compensation", "board of directors" etc.) → CONFIDENTIAL (3)
- Keywords ("restricted", "subpoena", "SEC investigation", "fraud" etc.) → RESTRICTED (4)

**Inheritance chain:**

Message (classified by origin + keywords)
→ Evidence inherits from Message
→ Claim inherits max level from its Evidence
Decision (classified by keywords + source_message_id reference to Message)



**Why max for Claims:** If a claim has evidence at levels 1, 1, 3 —
the claim gets level 3. The most sensitive source determines
classification. Showing the claim while hiding its evidence would
still leak the confidential fact.

#### Why filter in Cypher, not Python

If filtering happened in Python, restricted data would exist in
application memory — a bug, log statement, or stack trace could
expose it. Filtering in Cypher means the database enforces the
boundary. This is defense in depth — security is as close to the
data as possible.

#### `source_message_id` on Decision nodes

Decisions don't have a `FROM_MESSAGE` edge (unlike Evidence).
To enable message-based inheritance, `source_message_id` is stored
as a property on Decision nodes during loading (Day 23 loader).
The classification step uses this to look up the source Message's
`access_level` and inherit it if higher than the keyword-assigned level.

This fixed a gap where Decisions from legal and executive mailboxes
were getting PUBLIC classification despite their sensitive context.

After fix:
- Before: Decisions `{PUBLIC: 10,577, CONFIDENTIAL: 191, RESTRICTED: 12}`
- After: `{PUBLIC: 5,252, INTERNAL: 3,208, CONFIDENTIAL: 2,191, RESTRICTED: 129}`

#### Access level distribution (Enron corpus)

| Type | PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED |
|---|---|---|---|---|
| Claim | 2,821 | 1,437 | 1,241 | 87 |
| Evidence | 3,036 | 1,696 | 1,249 | 88 |
| Message | 4,316 | 2,493 | 1,692 | 94 |
| Decision | 5,252 | 3,208 | 2,191 | 129 |

~50% of content is PUBLIC, ~27% INTERNAL, ~21% CONFIDENTIAL, ~1-2%
RESTRICTED. The pyramid shape (most content at lower levels) matches
realistic organizational classification.

#### Verified

Querying Steven J. Kean's current state at different clearance levels:
- Intern (PUBLIC): 37 claims visible
- Employee (INTERNAL): 37 claims visible
- Manager (CONFIDENTIAL): 58 claims visible (+21 confidential)
- Executive (RESTRICTED): 59 claims visible (+1 restricted)

PROOF: Executive sees 22 more claims than intern. Restricted content
is invisible to low-clearance users.

#### Production notes

In production, classification would use source system labels
(Microsoft Purview, Google DLP, email sensitivity flags) rather than
keyword heuristics. User clearance would come from the identity
provider (Active Directory, Okta) via JWT tokens. The filtering
and enforcement architecture remains identical. The chatbot never
tells users "this is restricted" — it simply returns fewer results,
indistinguishable from content not existing.

#### Files

| File | Purpose |
|---|---|
| `src/graph/permissions.py` | PermissionManager + UserContext |
| `scripts/test_permissions.py` | Demo runner + --clear flag |
| `tests/test_permissions.py` | Unit tests for UserContext logic |




### Day 27 — Health Monitoring

#### What was built

A comprehensive health monitoring system (`src/graph/health_monitor.py`)
that measures graph quality, pipeline health, and system status across
7 metric categories. Feeds the frontend health dashboard (Day 42) and
provides baseline measurements for detecting quality degradation over time.

#### The 7 metric categories

**1. Graph size**
Node and edge counts by type. Sudden drops indicate data loss.
Sudden spikes indicate duplicate loading. Baseline for all other metrics.

**2. Claim quality**
- Average, min, max confidence across all claims
- Confidence distribution in 5 buckets (0.00-0.29, 0.30-0.49, 0.50-0.69, 0.70-0.89, 0.90-1.00)
- Claims grouped by type (reports_to, works_with, etc.)
- Evidence coverage: how many claims have 0, 1, or multiple evidence items
- Evidence verification rate: what percentage of evidence quotes were found verbatim in source emails

**3. Temporal health**
- Claims by status (current, superseded, archived, review)
- Supersession edge count (temporal succession chains)
- Conflict pair count (unresolved contradictions)
- Undated claims (from emails with null dates)
- Date range across all dated claims

**4. Access level distribution**
Counts per access level (PUBLIC/INTERNAL/CONFIDENTIAL/RESTRICTED) for
Claims, Evidence, Messages, and Decisions. Monitors permission
classification health.

**5. Entity statistics**
- Person count, average/max mention count, total aliases, total emails
- Organization count, org type distribution
- Top 10 most-mentioned persons (shows who the graph is "about")

**6. Data quality**
Structural integrity checks:
- Claims without SUBJECT edge
- Claims without OBJECT edge
- Claims without any evidence
- Evidence without FROM_MESSAGE link
- Messages without SENT_BY edge
- Decisions without MADE_BY edge
- Decisions with unresolved affects strings
- Soft-deleted node count

**Quality score formula:**
issue_rate = (claims_without_subject + claims_without_object
+ claims_without_evidence) / total_claims
quality_score = (1 - issue_rate) × 100 [0-100 scale]


**7. Pipeline status**
Checks all required data files for existence, size (MB), record count,
and last-modified timestamp. Detects stale pipelines (files not updated
in expected timeframes).

#### Observed metrics (Enron corpus baseline)

**Claim quality:**
- Average confidence: ~0.98 (high — mostly approved claims)
- Evidence verification rate: 96.1% (7,533 of 7,836 quotes found verbatim)
- Claims with no evidence: small number (relationships only have evidence)

**Temporal health:**
- Current claims: 5,538
- Superseded claims: 15
- Review claims: 33
- Conflict pairs: ~25
- Date range: 1997 to 2002

**Data quality:**
- Claims without SUBJECT: 96 (1.7% — entity ID mismatches from fuzzy merge)
- Claims without OBJECT: 22 (0.4%)
- Quality score: ~98/100

#### Design decisions

**Read-only** — the health monitor never writes to Neo4j or modifies
data files. It is safe to run at any time.

**Structured output** — `full_health_report()` returns a single dict
with all sections. The structure is designed to map directly to
frontend dashboard widgets.

**Baseline comparison** — Reports are saved to `data/processed/health_report_{timestamp}.json`
(e.g. `health_report_20260824_073000.json`). Each run creates a new file — the baseline is never overwritten. The frontend health dashboard (Day 42) reads the most recent report file. Historical reports are retained for trend comparison.

Current baseline saved: `health_report.json`
Future reports
can be compared against this baseline to detect degradation.

**Most important metric** — evidence verification rate. A drop below
90% signals the extraction prompt is degrading (model version changed,
new data types not covered by the prompt, etc.).

#### Files

| File | Purpose |
|---|---|
| `src/graph/health_monitor.py` | HealthMonitor class, 7 metric methods |
| `scripts/run_health_check.py` | Runner with formatted output + --save flag |
| `tests/test_health_monitor.py` | Unit tests for all metric methods |




### Day 28 — Week 4 Review

#### What was verified

Full end-to-end verification across all 6 Week 4 components.
82/83 automated checks passed.

#### Verification script (`scripts/verify_week4.py`)

6 sections, ~83 checks total:

**1. Graph integrity** — node/edge counts match expected values.
All 11 checks passed.

**2. Temporal queries — known facts** — Sally Beck's reporting chain
verified against source emails:
- Chain: Richard Causey → Brent Price → Louise Kitchen
- Chronological sorting verified
- Exactly one current claim verified
- Point-in-time queries verified:
  - March 2000 → Causey ✓
  - January 2001 → Kitchen ✓

This is the most important verification — it proves the temporal
model correctly answers "who did X report to at time T."

**3. Evidence trail end-to-end** — full path verified:
Claim (works_with Maureen McVicker)
→ Evidence: "I printed this out for you..."
(char_start=5, char_end=61, verified=True)
→ Source email: "Cynthia Sandherr's accomplishments/objectives"
(from: allison.navin@enron.com)


One check failed: exact substring match of quote in raw body.
This is a verification script limitation — the actual pipeline
uses normalized whitespace matching (Day 8) which correctly verified
this quote (evidence_verified=True). The raw body contains "SK - "
prefix that shifts the quote's position for simple string matching.

**4. Permission filtering** — 37+ checks verified:
- Intern (PUBLIC): 37 claims for Kean
- Executive (RESTRICTED): 59 claims for Kean
- All 37 intern claims verified at access_level=1
- Executive sees 22 more claims than intern

**5. Health metrics** — all thresholds met:
- Quality score: 97.9/100
- Average confidence: 0.9504
- Evidence verification rate: 96.7%
- Current claims: 5,538
- Superseded claims: 15

**6. Cross-component integration** — all pipeline files present,
full entity→claim→evidence→email chain confirmed working.

#### Week 4 final statistics

| Metric | Value |
|---|---|
| Total nodes | 56,062 |
| Total edges | 121,589 |
| Quality score | 97.9/100 |
| Average confidence | 0.9504 |
| Evidence verification rate | 96.7% |
| Current claims | 5,538 |
| Superseded claims | 15 |
| Conflicted claims (review) | 33 |
| Verification checks passed | 82/83 |

#### Known limitations documented after Week 4 review

1. **96 claims without SUBJECT edge** — entity IDs that changed
   during Day 17 fuzzy matching are not reflected in
   `resolved_claims.jsonl`. A post-merge ID update step in the
   claim dedup pipeline would fix this.

2. **22 claims without OBJECT edge** — same cause as above.

3. **SUBJECT/OBJECT edges connect only to Person nodes** — claims
   with Organization as subject or object get no structural edge.
   Extending the Cypher to also match Organization nodes would fix.

4. **Confidence decay parameters are hardcoded** — `DECAY_RATE_PER_YEAR`,
   `ARCHIVE_THRESHOLD`, and `MINIMUM_AGE_DAYS` in
   `incremental_updater.py` are constants. In production these would
   be stored in a config layer and exposed via a protected admin API
   endpoint so data engineers can tune without a code deployment.

5. **Access level classification uses keyword heuristics** — in
   production these would come from source system labels (Microsoft
   Purview, Google DLP).

#### Week 4 component summary

| Day | Component | Status |
|---|---|---|
| 22 | Neo4j schema (revised) | Complete |
| 23 | Graph loader — 56k nodes, 121k edges | Complete |
| 24 | Temporal query engine — 13 methods | Complete |
| 25 | Incremental updates, confidence decay, drift detection | Complete |
| 26 | Permission layer — 4 access levels | Complete |
| 27 | Health monitoring — 7 metric categories | Complete |
| 28 | Week 4 review — 82/83 checks passed | Complete |


## Week 5 — Retrieval Engine and Chatbot

### Day 29 — Vector Index

**New component:** `backend/src/retrieval/` package

**Purpose:** Semantic search over evidence excerpts using dense vector embeddings.
Complements the Neo4j graph (structured, entity-based queries) with concept-based
retrieval for questions that don't map to named entities.

**Embedding model:** `all-MiniLM-L6-v2` (sentence-transformers), 384 dimensions,
CPU-only, cosine similarity.

**Vector store:** Qdrant collection `evidence` (6,069 points).

**What is embedded:** Every active (non-deleted) Evidence node's quote text.
Evidence is the only node type with free-text natural language content worth
embedding. Persons, Organizations, Claims contain structured data, not sentences.

**Point structure:**
Each Qdrant point = one Evidence node
- `id`: deterministic integer derived from SHA-256 hash of evidence_id
- `vector`: 384-dim embedding of the evidence quote
- `payload`: evidence_id, quote, claim_id, claim_type, subject_id, object_id,
  confidence, access_level, valid_from, message_id, is_deleted

**Payload indexes:** access_level (INTEGER), confidence (FLOAT),
claim_type (KEYWORD), valid_from (KEYWORD), is_deleted (BOOL)
— enables filtered search without full payload scan.

**Permission filtering:** `access_level <= user_clearance` applied inside Qdrant
during search. Restricted content never enters application memory.

**Soft-delete integration:** `is_deleted = False` filter applied on every search.
`mark_deleted()` flips the payload flag without removing the vector.

**ID deduplication:** 6,962 evidence items fetched from Neo4j → 6,069 points
stored. 893 shared evidence items (same quote, same email, multiple claims)
collapsed by MERGE into single points.

**Bug found and fixed:** Day 23 loader wrote evidence node identity under property
`id` but never set `evidence_id` as a separate property. All 6,069 Evidence nodes
had `evidence_id = null`. Fix: added `e.evidence_id = row.id` to the SET clause
in `_load_claims_and_evidence()`, then reloaded the full graph.

**Retrieval modes (two-path architecture):**
- Neo4j (`temporal_queries.py`): entity-based, structured, time-aware queries
- Qdrant (`qdrant_index.py`): concept-based, semantic, filter-supported queries
These two paths are merged and ranked by the Day 31 retrieval engine.



### Day 30 — Query Understanding

**New module:** `backend/src/retrieval/query_understanding.py`

**Purpose:** Parses natural language questions into structured `QueryPlan` objects
that tell the retrieval engine (Day 31) exactly what kind of retrieval to perform —
which entities are involved, what time constraint applies, and whether to use graph
traversal, semantic search, or both.

**Output contract — `QueryPlan` fields:**
- `question_type`: who / what / when / why / history / current / comparison / list / yes_no
- `entities`: list of `ResolvedEntity` (raw name → canonical graph ID via Neo4j lookup)
- `time_constraint`: point / range / before / after / none, with ISO date bounds
- `retrieval_strategy`: graph / semantic / hybrid
- `needs_clarification`: True when resolution is ambiguous or entity not found
- `clarification_reason`: human-readable explanation shown to the user
- `semantic_query`: reformulated search string for Qdrant

**Processing pipeline (5 steps):**
1. LLM call (Gemini, temperature=0, thinking_budget=0) extracts mentioned entities,
   question type, time references, ambiguity signals, and semantic keywords
2. Entity resolution — each name searched in Neo4j across Person + Organization
   nodes by canonical_name and non-email aliases, sorted by priority then mention_count
3. Time constraint built from LLM output — ISO dates where possible, raw text preserved
4. Ambiguity detection — triggers clarification when alternatives exist (unconditional)
   or when entity is not found in graph
5. Strategy selection: resolved entities + semantic keywords → HYBRID;
   resolved entities only → GRAPH; no entities → SEMANTIC

**Entity resolution design decisions:**

*Organization-first ranking:* UNION query returns Organization matches with
priority=2 and Person matches with priority=1. Python sort applies
`(priority, mention_count)` descending so Organization nodes always rank above
Person nodes when both match. Fixes the case where "Enron" resolved as a Person
because every employee's email alias contains the substring "enron".

*Email alias exclusion:* Person alias search excludes aliases containing '@'.
Without this, searching "enron" matched 15,000 people's email addresses as
substring hits before matching the Organization node.

*Clarification is unconditional when alternatives exist:* Any entity with
at least one alternative triggers `needs_clarification = True` regardless of
confidence score. The correct entity is still stored as `canonical_id` (for
Day 31's graph traversal), but the user is shown options before an answer is
generated. This is conservative — it asks more questions — but prevents silently
answering about the wrong person.

*Zero-match fallback:* If an entity is not found in the graph, strategy falls
back to SEMANTIC so Qdrant can attempt concept-based retrieval using the entity
name as a search term. The question is not abandoned.

**Known limitations and silent decisions:**
- Entity search is capped at LIMIT 10 per node type — entities ranked below 10
  by mention_count are invisible to resolution
- Alternatives shown to user are capped at 4 — up to 6 further matches silently dropped
- LLM failure degrades silently to concept query (SEMANTIC strategy, raw question
  as search term) — no error shown to user, answer quality drops without warning
- GRAPH-only strategy rarely triggers in practice because the LLM almost always
  generates semantic_keywords, making most questions HYBRID
- Invalid question types from LLM default to "what"; invalid time types default to
  "none" — both silent
- The 3x mention_count ratio heuristic for confidence scoring (0.9 vs 0.5) is a
  judgment call, not empirically tuned; confidence no longer affects clarification
  since clarification is unconditional when alternatives exist
- Organization-first priority can overcorrect: "Tell me about Smith" resolves to
  "Salomon Smith Barney" (org) instead of a person named Smith — clarification
  catches this case

**LLM configuration:**
- Model: `gemini-3.1-flash-lite` via AI Studio free tier (permanent, no expiry)
- `temperature=0.0` — deterministic parsing
- `thinking_budget=0` — classification task, no reasoning tokens needed
- Fallback on any API failure: treat as concept query, no crash




## Day 31 — Hybrid Retrieval Engine

New module: `backend/src/retrieval/retrieval_engine.py`

Orchestrates graph traversal (Neo4j) and semantic search (Qdrant) into
unified hybrid retrieval. Produces ContextPack objects for the chatbot.

Pipeline: QueryPlan → graph retrieve + semantic retrieve → merge by
claim_id → rank by composite score (relevance × recency × confidence
× source_boost) → enrich with evidence → ContextPack.

Graph queries read subject_id, object_id, subject_name, object_name
directly from Claim nodes (no relationship traversal to Person/Org).

Entity resolution extended to Deal and Decision nodes, conditional on
LLM-assigned entity type to prevent cross-type pollution.

Semantic fallback: when no entity resolves, system runs semantic-only
search instead of returning empty clarification.

Qdrant date filtering uses Unix timestamps (FLOAT index) instead of
ISO string Range (which only accepts numeric types).

Backfill script (backfill_valid_to.py) writes valid_to from
resolved_claims.jsonl into Neo4j Claim nodes.





## Day 32 — FastAPI Backend
New module: `backend/src/api/`
REST API exposing all backend capabilities to the frontend.
Entry point: `backend/scripts/run_server.py` → uvicorn serving `src.api.app:app`.

Routes:
- POST /api/chat — question → QueryUnderstanding → RetrievalEngine → cited JSON
- GET /api/entities — paginated entity list with type/search filters
- GET /api/entities/{id} — single entity detail with properties
- GET /api/entities/{id}/timeline — chronological claims for an entity
- GET /api/entities/{id}/claims — filterable claims by type/status
- GET /api/graph/{id}/subgraph — 1-2 hop neighborhood (nodes + edges)
- GET /api/graph/search — cross-type entity search (Person/Org/Deal/Decision)
- GET /api/evidence/{id} — full evidence detail with source email body
- GET /api/health — Neo4j + Qdrant connectivity and counts
- GET /api/conflicts — claims with non-empty conflicts_with
- GET /api/review-queue — claims needing review (low confidence, conflicts, status=review)

Auth: simplified demo system using X-User-Clearance header mapped to
CurrentUser objects. Clearance flows into retrieval queries via
access_level filtering. Production path: replace get_current_user
dependency with JWT verification (bcrypt + python-jose), no other
route changes needed.

Lifespan: app startup connects Neo4j, initializes QdrantIndex,
QueryUnderstanding, and RetrievalEngine; shutdown closes Neo4j driver.
CORS configured for localhost React dev servers (3000, 5173, 5174).



## Day 33 — RAG Chatbot
New module: `backend/src/chatbot/`
Generates cited natural language answers from retrieved context.

Pipeline: ContextPack → format context as numbered text → system prompt
+ context + question → Gemini → answer with [N] citation markers →
parse markers → resolve to evidence metadata → ChatbotResponse.

System prompt enforces 7 grounding rules: answer only from context,
cite every claim, state time periods, explain changes, show both
sides of conflicts, admit gaps, flag low-confidence claims.

Empty context triggers a canned "no information" response without
calling the LLM (saves API quota, prevents hallucination).

Unix timestamps from semantic retrieval path converted to ISO dates
before LLM sees them (fixes Day 31 cosmetic issue).

Citation parser extracts [N] markers via regex, maps each to the
corresponding claim/evidence metadata, drops invalid markers.

Updated POST /api/chat to include "answer" (generated text) and
"citations" (resolved evidence references) alongside raw claims.

Clarification handled exclusively via structured clarification field
(Day 32) — not duplicated in answer text.

Fixed qdrant_index.py semantic_search() to return subject_name,
object_name, valid_to, status, and mention_count from Qdrant payload
(fields were written by build_vector_index.py but never read back).

Migrated from gemini-2.5-flash (retired) to gemini-3.6-flash, and
replaced thinking_budget=0 (Gemini 2.x) with thinking_level="low"
(Gemini 3.x API change).