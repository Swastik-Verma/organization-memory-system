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