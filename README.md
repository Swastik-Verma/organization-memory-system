# Organizational Memory System — Enron Email Dataset

A production-grade organizational memory system that extracts structured 
knowledge from the Enron email dataset (~517,000 emails), stores it in a 
knowledge graph with full evidence trails, and exposes it via a natural 
language chatbot and interactive frontend.

**Stack:** Python/FastAPI · Neo4j · Qdrant · Sentence-Transformers · 
Gemini API · React/TypeScript · shadcn/ui · Docker Compose

---

## Progress Log

### Day 1 — Project Scaffold & Environment Setup
- Set up WSL2 Ubuntu environment with project at `~/Layer_10_Project2/`
- Connected VS Code via WSL extension
- Created full project folder structure (`backend/`, `frontend/`, `docker/`, `data/`)
- Installed Python dependencies in a virtual environment:
  - CPU-only PyTorch (installed before `sentence-transformers` to avoid CUDA bloat)
  - `sentence-transformers` (all-MiniLM-L6-v2 for embeddings, Week 5-6)
  - `google-genai` (Gemini API client, Week 2-3)
  - `pydantic`, `fastapi`, `uvicorn`, and supporting libraries
- Set up memory-safe `docker-compose.yml` with Neo4j and Qdrant (RAM-capped for 8GB WSL2)
- Downloaded and extracted Enron email dataset into `data/raw/maildir/`
- Verified Neo4j running via browser dashboard
- Key decision: dropped `mailparser` (incompatible with Python 3.12+), 
  using built-in `email` module instead

---

### Day 2 — Email Parsing Pipeline
- Built `backend/src/parsing/email_parser.py`:
  - Uses Python's built-in `email` module with `policy.default` 
    (modern header parsing)
  - Reads raw files in binary mode (`rb`) to handle legacy encodings safely
  - Extracts: `message_id`, `from_addr`, `to_addrs`, `cc_addrs`, 
    `subject`, `date`, `body`, `x_folder`, `x_origin`
  - `x_folder` and `x_origin` retained for future provenance and 
    entity-resolution work (Week 3-4)
  - MIME headers (`Content-Type`, `Mime-Version` etc.) deliberately 
    excluded — encoding plumbing, not content
- Built `backend/src/parsing/schema.py` — `ParsedEmail` Pydantic model:
  - Required fields: `message_id`, `from_addr`, `body`
  - Optional fields with safe defaults: `cc_addrs`, `subject`, 
    `x_folder`, `x_origin`
  - Custom `@field_validator` converts RFC 2822 date strings to Python 
    `datetime` objects using `email.utils.parsedate_to_datetime`
  - Malformed dates return `None` rather than crashing validation
- Built `backend/scripts/batch_parse_emails.py`:
  - Walks `data/raw/maildir/` recursively
  - Parses + validates each file against `ParsedEmail`
  - Separates `ValidationError` (data issues) from generic exceptions 
    (file/code issues)
  - Progress counter every 1,000 files
  - Saves results to `data/processed/parsed_emails.jsonl` (one JSON 
    object per line, using Pydantic's `model_dump_json()`)
- Key bug caught and fixed: `data/raw/` contained the original 
  `enron_mail_20150507.tar.gz` archive alongside the extracted `maildir/`. 
  File-discovery logic was picking up the ~1.5GB compressed archive and 
  trying to parse it as an email, locking up the 8GB WSL2 machine. 
  Fixed by scoping `raw_dir` to `data/raw/maildir/` directly.
- Connected project to GitHub with `.gitignore` correctly excluding 
  `.env`, `venv/`, `data/raw/`, and `data/processed/`

---

### Day 3 — Full Batch Parse, Data Quality & Hardening
- Added date plausibility filter to `ParsedEmail` schema:
  - Dates outside 1995–2005 treated as `None` (realistic Enron window)
  - Catches header typos / corrupted clock values in source data
- Ran full batch parse across all 517,401 files:
  - **Successfully parsed: 517,389 (99.998%)**
  - **Failed: 12 (0.002%)** — all from `kitchen-l` mailbox, caused by 
    a known Python `email` module edge case with malformed headers 
    (`ValueTerminal` object error). Deemed not worth fixing at this scale.
- Investigated duplicate `message_id` findings:
  - `check_duplicates.py` reported 0% duplication
  - Independent raw-text `grep` analysis appeared to show duplicates 
    (up to 64 occurrences of one ID)
  - Root cause identified: `grep` matched `Message-ID:` text inside 
    email *bodies* (forwarded/quoted content), not just top-level headers
  - Confirmed: `msg.get("Message-ID")` in parser correctly reads only 
    the true top-level header — 0% duplication finding is accurate
  - This dataset (as packaged) does not contain true header-level 
    duplicate emails — email-level merge logic not required for Week 3-4
- Built `backend/scripts/check_duplicates.py` — duplicate detection tool
- Built `backend/scripts/data_quality_report.py` — full pipeline QA report

**Final Data Quality Report:**

- Total files attempted:     517,401
- Successfully parsed:       517,389
- Failed to parse:           12
- Success rate:              99.998%
- Unique message_ids:        517,389
- Duplicate records:         0
- Records with valid date:   516,854
- Records with null date:    535 (0.10%)
- Earliest email date:       1997-01-01
- Latest email date:         2005-12-29

---

### Day 4 — LLM Extraction Pipeline (Complete)

- Built full Gemini-based extraction pipeline: schema (`LLMExtractionOutput` 
  + `ExtractionResult`), prompt engineering (v1 → v2, fixed 8 defects including 
  hallucinated message_ids, weak relationship evidence, and incorrect `made_by` 
  attribution), checkpointed batch extraction with automatic retry on temporary 
  errors (429/503/network disconnects)
- **Major deviation:** free-tier Gemini API rate limits turned out to be 20 
  requests/day (not the 1,500 documented), making free-tier extraction of 
  10,000 emails infeasible (~500 days). Pivoted to Google Cloud's $300 free 
  trial credit via **Vertex AI** (a different API surface than AI Studio, 
  since AI Studio usage is excluded from the credit)
- **Final model:** `gemini-3.1-flash-lite` via Vertex AI (`location="global"`), 
  `thinking_budget=0` to avoid billing for unused reasoning tokens
- **Subset:** 10,000 emails drawn from 10 key Enron mailboxes (Kaminski, 
  Dasovich, Kean, Mann, Jones, Beck, Nemec, Kitchen, Lay, Arnold), capped at 
  1,500/person for balanced representation
- **Result:** 10,000 / 10,000 emails successfully extracted
- **Actual cost:** $[FILL IN FROM BILLING CHECK]
- Extraction totals: [FILL IN FROM extraction_quality_report.py OUTPUT — 
  e.g. total people/orgs/deals/decisions/relationships extracted]
- **Known limitation carried to Week 4–5:** `affects` field on decisions is 
  a free-text list mixing people, orgs, systems, and generic placeholders — 
  must be resolved against `people`/`organizations` at graph-ingestion time, 
  not at extraction time (see project context doc §9.1)

- Extraction Quality Report of Day 4 is (it is not the full report, for full report run scritps/extraction_quality_report.py):
```
=======================================================
EXTRACTION QUALITY REPORT
=======================================================
Total emails extracted:      10000

Total people mentions:       98611
Total organizations:         28723
Total deals:                 4781
Total decisions:             12331
Total relationships:         7837

Avg people/email:            9.86
Avg decisions/email:         1.23
Avg relationships/email:     0.78

Decisions with made_by=null: 384 (3.1% of decisions)

Relationship types breakdown:
  works_with           3419
  requests_from        2824
  informs              867
  reports_to           546
  negotiating_with     181
=======================================================
```

### Day 5 — Graph Ontology & Neo4j Schema Design
- Designed the knowledge graph ontology with reified claims (relationships stored as nodes, not direct edges) to support evidence trails, temporal validity windows, supersession links, and confidence scores
- Defined 7 node types: Person, Organization, Deal, Decision, Claim, Evidence, Message
- Chose deterministic ID strategy (slugified names for entities, SHA-256 hashes for claims/evidence) to enable idempotent graph rebuilds via MERGE
- Defined temporal model: valid_from = email date (first observed), valid_to = null until contradicted; 535 null-date emails excluded from point-in-time queries but included in full-history queries
- Created Pydantic models for all graph node types (`backend/src/graph/schema.py`)
- Applied 7 uniqueness constraints and 13 indexes to Neo4j (`backend/scripts/init_graph_schema.py`)
- Documented all design decisions and rejected alternatives in `docs/ONTOLOGY.md`
- Ran extraction quality inventory: 44k estimated nodes, 42k relationships — comfortable within 512MB Neo4j heap cap
- Key findings from data inventory: org_type needs normalization (120+ variants → 6 categories), affects resolution rate is 91.3% (§9.1 problem smaller than expected), closed relationship vocabulary held perfectly


### Day 6 — Noise Detection, Thread Reconstruction & Chunking Analysis
- Re-parsed all 517,389 emails with new fields: in_reply_to, references, x_from_display, x_to_display, x_cc_display
- Discovered In-Reply-To/References headers are absent from this packaged Enron dataset — fell back to subject-line threading
- Built noise detector (`backend/src/parsing/noise_detector.py`) identifying quoted reply blocks, forwarding headers, and signature footers by character offset — used downstream to flag evidence extracted from non-original content
- Built thread reconstructor (`backend/src/parsing/thread_reconstructor.py`) grouping emails by normalized subject line: 159,886 threads (84,760 multi-message, largest thread 1,124 messages)
- Analyzed body length distribution: P99 = 3,057 tokens, max = 34,188 tokens — chunking confirmed unnecessary as all emails fit within Gemini flash-lite's context window
- Regenerated extraction_subset.jsonl with new parsed fields


### Day 7 — Week 1 Review, Testing & Documentation
- Ran full ingestion pipeline end-to-end: parse → subset selection → noise detection → thread reconstruction
- Verified noise detector on 500 emails: confirmed detection of forwarding headers, quoted replies, and signatures
- Manually reviewed 20 email outputs checking noise detection accuracy
- Wrote unit tests for ParsedEmail schema, noise detector, and thread reconstructor subject normalization (tests/test_parsing.py)
- Documented ingestion layer guarantees — what the pipeline promises about its output and what it does not
- Week 1 complete: clean, structured, threaded email data ready for extraction pipeline improvements in Week 2


### Day 8 — Evidence Verification & Offset Computation
- Built evidence verifier: whitespace-normalized matching of LLM evidence quotes
  against source email bodies
- Computed character offsets (char_start/char_end) for verified quotes, enabling
  frontend evidence highlighting
- Verification rate: 96.1% (7,533/7,836 quotes verified)
- 303 unverified quotes flagged for confidence penalty — not deleted
- Added unit tests for graph schema models and evidence verifier
- Output: `extractions_with_offsets.jsonl`, `evidence_verification_report.json`


### Day 9 — Confidence Scoring
- Built deterministic confidence scorer: field-aware penalties from verifiable
  signals (evidence verification, quote length, noise regions, entity completeness)
- Scored all 152,283 extracted items; average confidence 0.889, median 0.90
- Relationships score highest (0.942) due to verified evidence; people lowest (0.879)
  due to frequent missing email addresses
- 99.98% of items above 0.7 soft threshold
- Output: `extractions_scored.jsonl`, `confidence_report.json`

### Day 10 — Extraction Versioning & Repair Loop
- Built version manager: SHA-256 prompt hashing, stale extraction detection,
  version reporting
- Retroactively stamped all 10,000 extractions with prompt hash and model name
- Added repair-retry loop to extractor: sends validation errors back to LLM
  for structural fixes (up to 2 attempts)
- Added raw LLM response storage for debugging
- Output: `extractions_versioned.jsonl` (fully enriched with offsets, confidence,
  and version stamps)


### Day 11 — Quality Gates
- Built three-tier quality gate: approved / review / rejected
- Added structural hard-reject rules that bypass confidence scoring
  (missing identity fields, invalid relationship types, self-referential
  relationships, unverifiable short evidence)
- Confidence thresholds: soft=0.70, hard=0.30
- Generated review queue for items needing human judgment
- Output: `extractions_gated.jsonl`, `review_queue.jsonl`,
  `quality_gate_report.json`


### Day 12 — Unified Pipeline & Re-extraction Runner
- Consolidated four enrichment scripts into a single unified pipeline
  (verify → score → gate → stamp) producing one canonical output file
- Built re-extraction runner for selective re-processing when prompt changes
- Added pipeline integration tests verifying end-to-end enrichment
- Output: `extractions_final.jsonl` (canonical enriched file),
  `pipeline_report.json`



### Day 13 — Extraction Quality Evaluation
- Manually evaluated 50 random extractions against source emails
- Overall accuracy: [X]%, hallucination rate: [Y]%
- Top failure modes: [list your actual top 3]
- Automated failure analysis of 303 unverified quotes, 22 review items,
  and 6 rejected items
- Output: `extraction_quality_report.json`, `failure_analysis.json`

### Day 14 — Week 2 Review
- Wrote formal extraction contract (docs/EXTRACTION_CONTRACT.md) defining
  6 guarantees and 5 explicit non-guarantees
- Exported example outputs to data/outputs/ for repo inclusion
- Added unit tests for checkpoint module and prompt validation
- Full test suite: [N] tests passing across 10 test files
- Completed Week 2: extraction pipeline is fully tested, documented,
  and ready for Week 3 deduplication


### Day 15 — Artifact Deduplication

Built the artifact deduplication pipeline to detect exact and near-duplicate
emails before graph ingestion.

- **Exact duplicates** (SHA-256 of whitespace-normalized body): 833 groups,
  907 duplicate emails. These are the same email appearing in multiple
  mailbox folders (e.g. Sent + Discussion threads) with different Message-IDs
  but identical content.
- **Near-duplicates** (cosine similarity ≥ 0.95 via all-MiniLM-L6-v2):
  170 groups, 498 duplicate emails. These are forwards and cross-posts
  with minor additions ("FYI", different forwarding headers).
- **Result:** 1,405 emails flagged as duplicates → 8,595 unique emails
  will be loaded into Neo4j.
- Duplicate IDs saved to `duplicate_ids.json` for O(1) lookup during ingestion.

Note: Day 3 reported 0% duplicates because it checked `message_id` uniqueness
(header-level). Day 15 checks body-level content, which correctly identifies
the same content filed under different Message-IDs across mailbox folders.





### Day 16 — Entity Resolution (Exact Matching)

Built the entity resolution pipeline to collapse multiple name strings
referring to the same person or organization into canonical entities.

**Two resolution strategies (priority order):**
1. **Email match** (people only): if two names share the same email address,
   they are definitively the same person (confidence 1.0)
2. **Normalized name match**: lowercase, strip titles, sort parts for people;
   strip corporate suffixes for organizations (confidence 0.95)

**Safeguards implemented:**
- Names with same normalized form but different emails are kept separate
  (genuinely different people who share a name)
- Shared/generic email addresses (5+ distinct names) are excluded from
  email-based resolution to prevent false merges
- Multi-candidate name matching picks the highest-mention entity when
  disambiguation is impossible

**Results:**
- 17,046 unique person names → 16,095 canonical people (951 collapsed)
- 7,472 unique org names → 6,925 canonical organizations (547 collapsed)
- 2,024 total merges: 1,262 by email, 762 by normalized name
- 4 shared emails detected and excluded
- Resolution map saved for downstream ingestion (24,252 name→id mappings)

Known remaining duplicates (Day 17 targets): "Kenneth Lay" split across
two emails (`klay@enron.com` / `kenneth.lay@enron.com`), same for
Vince Kaminski across `vkamins@enron.com` / `vkamins@ect.enron.com`.
Nicknames ("Ken" vs "Kenneth") also remain unmerged.


### Day 17 — Entity Resolution (Fuzzy Matching + Undo)

Built the fuzzy entity matching pipeline on top of Day 16's exact matching.
Four strategies surface merge candidates that exact matching missed:

1. **Middle initial stripping** (743 candidates): "Steven J Kean" → "Steven Kean"
2. **Nickname expansion** (323 candidates): "Ken Lay" → "Kenneth Lay"
3. **Same email domain** (490 candidates): same name + same @enron.com domain
4. **General fuzzy matching** (1,803 candidates): catches typos via rapidfuzz

Total: 2,503 unique candidates. Candidates ≥ 0.85 confidence are
auto-merged; 0.70–0.85 saved for human review in Week 7; below 0.70
skipped. All auto-merges are undoable via stored pre-merge snapshots.

Built full undo capability: every merge operation stores pre-merge snapshots
of both entities. Any merge can be reversed, restoring both entities to
their exact prior state.


### Day 18 — Claim Deduplication

Collapsed 6,963 extracted relationships into 5,586 unique facts by
resolving name variants to canonical IDs and merging duplicate mentions.

**Three phases:**
1. **Resolve and group:** All person names resolved via Days 16-17
   resolution map. Symmetric types (works_with, negotiating_with)
   normalized so "A works_with B" and "B works_with A" merge correctly.
   Grouped by (subject_id, relationship_type, object_id).
2. **Merge evidence:** Each group becomes one DedupedClaim with all
   supporting evidence accumulated. Claim confidence = max across
   evidence items. valid_from = earliest email date.
3. **Detect conflicts:** Flags cases where the same person has multiple
   different objects for reports_to (exclusive type). 27 genuine
   conflicts detected for Day 19 classification.

**Results:**
- 6,963 relationships → 5,586 unique claims (1.25x compression)
- 744 claims backed by multiple evidence items
- Top claim: "Kay Mann requests_from Suzanne Adams" (17 supporting emails)
- 27 reports_to conflicts flagged for Day 19
- 0 unresolved person references



### Day 19 — Conflict Resolution

Classified and resolved the 27 reports_to conflicts detected in Day 18.

**Classification logic (based on valid_from dates):**
- Different dates → temporal succession (auto-resolve)
- Same date → direct contradiction (human review)
- Missing date → undated (human review)

**Results:**
- 16 temporal successions auto-resolved: older claim gets valid_to closed
  at the newer claim's valid_from date, marked "superseded". A SUPERSEDES
  edge connects them in the graph.
- 11 direct contradictions flagged for human review. Both claims marked
  "review" with bidirectional CONFLICTS_WITH edges.
- 22 claims now have closed validity windows (valid_to set)
- 60 decisions flagged as potential reversals via keyword patterns
  (e.g. "cancelled", "no longer", "reversed")

Notable finding: "Brent Price reports_to" shows a 4-step reporting chain
change (Beck → Dyson → Causey → ENA Office of Chairman), demonstrating
the temporal model capturing real Enron organizational evolution.

Canonical output: resolved_claims.jsonl (supersedes deduplicated_claims.jsonl)




### Day 20 — Soft Deletes and Redaction

Built the RedactionManager library for safe, auditable data removal.
Three operations with different severity levels:

1. **Soft delete entity**: Flags entity + cascades to all connected claims
   and evidence. Fully reversible via restore.
2. **Soft delete claim**: Flags one claim + its evidence. Does not cascade
   to entities (a person survives deletion of one fact about them).
3. **Redact entity**: Replaces all content with [REDACTED], then soft-deletes.
   Irreversible — for legal/privacy compliance where content must be
   provably destroyed.

Core principle: nothing is ever hard-deleted. Deleted items remain in the
graph with is_deleted=True, excluded from queries but preserved for audit.
Cascade tracking via deletion_reason prefix enables precise restore —
only claims deleted because of a specific entity are restored with it.

No batch script — this is a library called by the FastAPI API (Day 32)
and the React frontend (Week 7) in response to user actions.



### Day 21 — Week 3 Review

Ran end-to-end verification of the full deduplication pipeline (Days 15-20).

**Verification results:**
- All output files present and correctly structured
- Cross-stage data integrity verified (claim IDs unique, entity references
  resolved, supersession chains consistent)
- Soft delete round-trip tested (delete → verify hidden → restore → verify back)
- 20 entity merges manually reviewed — all correct
- 20 claim dedup decisions manually reviewed — all correct

**Week 3 summary:**
- 10,000 emails → 8,595 unique (Day 15: 1,405 duplicates removed)
- 17,046 person names → 16,095 canonical people (Day 16: 951 collapsed)
- 7,472 org names → 6,925 canonical organizations (Day 16: 547 collapsed)
- 2,503 fuzzy merge candidates identified (Day 17: saved for Week 7 review)
- 6,963 relationships → 5,586 unique claims (Day 18: 1.25x compression)
- 27 conflicts → 16 auto-resolved, 11 for human review (Day 19)
- Soft delete + redaction manager built with cascading and restore (Day 20)

Data is ready for Week 4: Neo4j ingestion.



### Day 22 — Neo4j Schema (Revised)

Revised the Neo4j graph schema from Day 5 to match three weeks of
data evolution. Updated Pydantic models in `src/graph/schema.py`
to reflect the new Person ID format (includes email slug to handle
same-name collisions), the new fact-level Claim ID scheme from Day 18,
and the temporal fields added in Day 19 (`supersedes`, `superseded_by`,
`conflicts_with`). Added `normalize_org_type()` to map 120+ free-text
org_type variants to 6 clean categories.

Ran `init_graph_schema.py --drop-existing` to replace the Day 5
schema: dropped 7 old constraints and 13 old indexes, created 7 new
constraints and 20 new indexes. Graph is now empty and ready for the
loader in Day 23.

Graph size estimate after loading: ~50k nodes, ~100k edges —
comfortably within the 512MB Neo4j heap cap.




### Day 23 — Graph Loader

Built the graph loader (`src/graph/loader.py`) that reads all four
Week 2-3 data files and loads them into Neo4j using idempotent MERGE
operations. Loading completes in ~35 seconds.

**What was loaded:**
- 56,062 nodes across 7 types (Person, Organization, Message, Deal,
  Decision, Claim, Evidence)
- 121,589 edges across 11 types

**Key design decisions:**
- MERGE throughout — re-running produces identical results, no
  duplicates created
- UNWIND batching (500 items per transaction) — eliminates per-node
  network overhead
- Duplicate email filtering applied to Deal and Decision loading —
  reduced decisions from 12,331 raw to 10,780 clean
- Resolution at load time — `affects`, `made_by`, `parties_involved`
  resolved via `resolution_map.json`; unresolved strings stored as
  text properties (`affects_unresolved`, `parties_unresolved`),
  never as phantom nodes
- Evidence IDs and Deal IDs generated deterministically at load time
  (sha256-based) since these have no pre-existing IDs in the pipeline

**Graph is now queryable at http://localhost:7474**

Example query — full reporting history for a person:
```cypher
MATCH (p:Person)
WHERE p.canonical_name CONTAINS "Kean"
WITH p
MATCH (c:Claim {claim_type: "reports_to"})-[:SUBJECT]->(p)
MATCH (c)-[:OBJECT]->(boss:Person)
RETURN boss.canonical_name, c.valid_from, c.valid_to, c.status
ORDER BY c.valid_from
```


### Day 24 — Temporal Query Engine

Built the query layer (`src/graph/temporal_queries.py`) that sits
between the chatbot and Neo4j. All graph queries go through this
module — the chatbot never writes raw Cypher.

**Three core temporal access patterns:**
- `get_current_state()` — what is true right now (`valid_to IS NULL`)
- `get_state_at(date)` — what was true at a specific date
- `get_full_history()` — complete chronological record

**13 methods total** covering entity lookup, evidence retrieval,
decisions, deals, conflict queries, and graph statistics.

**Four concerns handled automatically on every query:**
temporal filtering, soft-delete exclusion, entity resolution by
partial name, and clean result formatting.

**Verified against real data.** Sally Beck's full reporting history
correctly shows the supersession chain Causey → Price → Kitchen
with validity windows. Evidence trail works end-to-end from claim
to quote to source email. Graph statistics confirmed:
15,003 persons, 5,586 claims (5,538 current, 15 superseded, 33 review).



### Day 25 — Incremental Update System

Built three production-readiness features in
`src/graph/incremental_updater.py`:

**1. Incremental updates (`run_incremental_update`)**
Loads new email batches into the existing graph without touching old
data. MERGE makes it idempotent — reprocessing an existing email
updates rather than duplicates. After loading, automatically detects
conflicts between new and existing claims.

**2. Confidence decay (`apply_confidence_decay`)**
Ages out stale claims using a time-based formula: 10% confidence
lost per year without fresh supporting evidence. Claims that drop
below 0.30 confidence are archived rather than deleted. Reversible
via `reset_confidence_decay()` or by re-running the graph loader.
A dry-run preview mode (`preview_confidence_decay`) shows affected
claims before committing changes.

**3. Ontology drift detection (`detect_ontology_drift`,
`detect_graph_drift`)**
Monitors for schema violations — relationship types outside the
5-type closed vocabulary, org types that don't map to the 6
categories, structural issues (self-referential relationships,
missing endpoints). Reports findings without blocking. Human decides
whether to fix the prompt, expand the ontology, or ignore noise.

**Note on portfolio project usage:**
The Enron corpus is historical (ends ~late 2001). These features
are built and tested but not actively applied — running decay on
a frozen corpus would archive valid claims with no new emails to
replenish confidence. The code demonstrates the production
architecture for the organizational memory system and is fully
explainable in technical interviews.

**How the full incremental pipeline would work in production:**

New emails → parse → LLM extract → enrich → entity resolve
→ claim dedup → conflict resolve → run_incremental_update (load)
→ apply_confidence_decay (schedule) → detect_graph_drift (health)


### Day 26 — Permission Layer

Built role-based access control over the knowledge graph
(`src/graph/permissions.py`).

**Four clearance levels:** PUBLIC (1), INTERNAL (2), CONFIDENTIAL (3),
RESTRICTED (4). Rule: `content.access_level <= user.clearance_level`.

**Classification applied to:** Messages (mailbox origin + keywords),
Evidence (inherits from source message), Claims (inherits max level
from evidence), Decisions (keywords + source message inheritance via
`source_message_id` property added to Decision nodes).

**Key design:** Filtering happens inside Cypher — restricted content
never leaves Neo4j for unauthorized users. An intern and a VP asking
the same chatbot question get different answers without either knowing
why. The chatbot never says "this is restricted" — it simply returns
fewer results.

**Verified on Enron corpus:**
- Intern (PUBLIC clearance): sees 37 claims about Steven J. Kean
- Executive (RESTRICTED clearance): sees 59 claims
- Proof: executive sees 22 more claims than intern

**Access level distribution after classification:**
Claims: 2,821 PUBLIC | 1,437 INTERNAL | 1,241 CONFIDENTIAL | 87 RESTRICTED

In production: source system labels (Microsoft Purview, Google DLP)
replace keyword heuristics; user clearance comes from identity
provider (Active Directory, Okta) via JWT tokens.


### Day 27 — Health Monitoring

Built a comprehensive health monitoring system
(`src/graph/health_monitor.py`) that measures graph quality and
pipeline health across 7 categories.

**7 metric categories:**
- **Graph size** — node/edge counts by type (baseline for degradation detection)
- **Claim quality** — confidence distribution, evidence coverage, verification rate
- **Temporal health** — status distribution (current/superseded/review), conflict count
- **Access levels** — permission classification distribution per content type
- **Entity stats** — person/org counts, org types, top 10 most-mentioned entities
- **Data quality** — structural issues (missing edges, unlinked nodes), quality score
- **Pipeline status** — data file freshness, sizes, record counts

**Quality score:** Single 0-100 metric based on structural issue rate.
Current baseline: ~98/100 (96 claims with missing SUBJECT edge out
of 5,586 total = 1.7% issue rate).

**Most important metric:** Evidence verification rate (96.1%) —
measures whether extracted claims are grounded in actual source text.
A drop signals extraction prompt degradation.

**Safe to run at any time** — health monitor is read-only.
Use `--save` to persist the report for baseline comparison:

```bash
python scripts/run_health_check.py --save
# Current Baseline Report saved to data/processed/health_report.json
# Future Reports saved to data/processed/health_report_{timestamp}.json
# Each run creates a new timestamped file — baseline is preserved.
# Day 42 frontend reads the most recent report for the health dashboard.
```

Feeds the frontend health dashboard (Day 42): confidence histogram,
claims-by-status donut chart, top entities list, data quality table.


### Day 28 — Week 4 Review

Week 4 review and verification. 82/83 automated checks passed
across all 6 Week 4 components.

**Verification script (`scripts/verify_week4.py`) covers:**
- Graph integrity (11 checks) — node/edge counts match expectations
- Temporal queries (9 checks) — Sally Beck's reporting chain
  (Causey → Price → Kitchen) verified against source emails with
  correct point-in-time behavior
- Evidence trail (8 checks) — full path from claim to source email
  working end-to-end
- Permission filtering (37+ checks) — intern sees 37 claims,
  executive sees 59, all intern claims confirmed at PUBLIC level
- Health metrics (8 checks) — 97.9/100 quality score, 96.7%
  verification rate, all thresholds met
- Cross-component integration (6 checks) — all pipeline files
  present, full chain confirmed working

**The one failed check:** exact substring quote matching in raw
email body — a verification script limitation (uses simple `in`
operator) vs the actual pipeline which uses normalized whitespace
matching. The evidence_verified flag is True for the same quote.

**Week 4 final state:**
- 56,062 nodes, 121,589 edges
- Quality score: 97.9/100
- Average confidence: 0.9504
- Evidence verification rate: 96.7%
- 5,538 current claims, 15 superseded, 33 in review

**Ready for Week 5:** Retrieval engine and chatbot.



## Week 5 — Retrieval Engine

### Day 29 — Vector Index

Built semantic search over the 6,069 evidence excerpts extracted from Enron emails.

**Stack addition:** Qdrant vector database (`src/retrieval/qdrant_index.py`)

**How it works:**
Each evidence quote is converted into a 384-dimensional vector using the
`all-MiniLM-L6-v2` sentence-transformer model (CPU-only). These vectors are stored
in Qdrant alongside metadata (access level, confidence, claim type, entity IDs,
soft-delete flag) enabling filtered semantic search.

**Semantic search respects permissions:** The access level filter is applied
inside Qdrant during the vector search itself — restricted content is never
returned regardless of query.

**To rebuild the vector index:**
```bash
cd backend
python scripts/build_vector_index.py --recreate
```

**Sanity check results:**
Query: "California energy trading"
- score=0.71 — "you asked for a California energy expert"
- score=0.64 — "Northern California Electricity Prices"
- score=0.60 — "California power prices next summer"



### Day 30 — Query Understanding

Built the layer that sits between a user's raw question and the retrieval
engine — parsing natural language into a structured retrieval plan.

**What it does:**
Every user question goes through a 5-step pipeline:
1. Gemini parses the question → extracts entity names, question type,
   time references, ambiguity signals
2. Each entity name is resolved to a canonical Neo4j ID via name + alias search
3. A time constraint is built (point / range / before / after / none)
4. Ambiguity is detected — if multiple graph matches exist, the user is asked
   to clarify before retrieval runs
5. Retrieval strategy is chosen: graph (Neo4j traversal), semantic (Qdrant),
   or hybrid (both)

**Example outputs:**

"Who did Sally Beck report to in March 2001?"
→ type=who, entity=person:beck-sally:..., time=point(2001-03-01), strategy=hybrid

"What concerns were raised about California energy prices?"
→ type=what, no entity resolved, strategy=semantic

"Tell me about Smith."
→ needs_clarification=True, 4 options shown to user

**Key design decisions:**
- Organization nodes rank above Person nodes in entity search — prevents
  email address substring matches from swamping organization name matches
- Clarification is unconditional when alternatives exist — never silently
  picks the wrong person
- LLM failure degrades gracefully to semantic search — no crash, reduced quality
- Switched from Vertex AI to AI Studio free tier (permanent quota,
  no expiry concerns)

**To test:**
```bash
cd backend
python scripts/test_query_understanding.py           # batch test, 10 questions
python scripts/test_query_understanding.py -i        # interactive mode
```



### Day 31 — Hybrid Retrieval Engine
- `retrieval_engine.py`: orchestrates graph + semantic retrieval, merges
  and ranks results into ContextPack for chatbot consumption
- `backfill_valid_to.py`: one-time script to populate valid_to on Claims
- Fixed Claim property names (c.id not c.claim_id, direct subject/object
  fields instead of relationship traversal)
- Fixed Qdrant date filtering (Unix timestamps instead of string Range)
- Fixed min_should Filter construction (removed, Qdrant defaults to 1)
- Extended entity resolution to Deal and Decision nodes
- Added semantic fallback when entity resolution returns nothing
- Updated QUERY_PARSE_PROMPT with correct 5 claim types




### Day 32 — FastAPI Backend
- `src/api/app.py`: FastAPI app with lifespan management and CORS
- `src/api/dependencies.py`: shared resource injection and demo auth
- `src/api/models.py`: Pydantic request/response schemas
- `src/api/routes/`: chat, entities, graph, evidence, health, admin endpoints
- `scripts/run_server.py`: CLI entry point with --host, --port, --reload
- Swagger docs at http://localhost:8000/docs
- Demo auth via X-User-Clearance header (JWT-ready architecture)




### Day 33 — RAG Chatbot
- `src/chatbot/prompts.py`: system prompt with 7 grounding rules
- `src/chatbot/chatbot.py`: answer generation with citation parsing
- Updated `POST /api/chat` to return generated answer + resolved citations
- Added CitationItem model, get_chatbot dependency, chatbot startup init
- Empty context returns canned response (no LLM call)
- Unix timestamp cleanup for LLM-readable dates
- Fixed semantic_search() to return all payload fields (subject_name,
  object_name, valid_to, status, mention_count were written but never read)
- Migrated to gemini-3.6-flash with thinking_level="low" (3.x API)




### Day 34 — Multi-turn Conversation
- `src/chatbot/conversation.py`: ConversationMemory + FollowUpResolver
- Added FOLLOW_UP_REWRITE_PROMPT to prompts.py
- Updated chat route with session tracking and follow-up rewriting
- Added session_id and effective_question to ChatRequest/Response
- Regex heuristic detects pronouns, temporal fragments, topic continuations
- LLM rewriter only called when heuristic fires (saves API quota)
- Bounded 5-turn history window per session


### Frontend

React + Vite + TypeScript application in `frontend/`.

**Tech stack:** Tailwind CSS, shadcn/ui, react-router-dom

**Run the dev server:**
```bash
cd frontend
npm install
npm run dev
```

**Pages:** Chat, Graph Explorer, Entities, Entity Detail, Evidence, Health Dashboard, Conflict Review, Merge Audit Log





### Running the Full Stack

1. Start databases:
```bash
   docker compose up -d
```

2. Start backend:
```bash
   cd backend && source venv/bin/activate
   python scripts/run_server.py
```

3. Start frontend:
```bash
   cd frontend && npm run dev
```

4. Open http://localhost:5173 in your browser.

**Note:** If the backend server fails to start silently (no error but changes not
reflected), check whether a previous server process is still holding port 8000:
```bash
lsof -i :8000
```
Kill the stale process before restarting.

### API Integration

The frontend connects to the FastAPI backend at `http://localhost:8000`. All API calls
are centralized in `frontend/src/lib/api.ts`. Entity IDs contain colons and are
URL-encoded in all API paths.

**Quota note:** The `/api/chat` endpoint calls Gemini (currently `gemini-3.1-flash-lite`)
on every request. All other endpoints (entities, graph, evidence, health) only query
Neo4j/Qdrant and do not consume LLM quota.





### Health Dashboard (`/health`)
System monitoring page showing knowledge graph quality at a glance. Six summary
cards (emails processed, total entities, total claims, quality score, average
confidence, evidence verification rate), a confidence distribution histogram
and claims-by-type horizontal bar chart (Recharts), live service status for
Neo4j and Qdrant with real error messages on failure, pending review and
conflict pair counts linked to their respective pages, claims-by-status
breakdown, and a top-10 most-mentioned entities table. Graceful degradation:
if the full health report fails but basic connectivity succeeds, every
report-dependent card shows a clear "metrics unavailable" message instead of
crashing or displaying zeros. Manual refresh button — no auto-polling, since
the corpus is frozen and metrics don't change between requests.

**Backend change (Day 42):** `/api/health` expanded to return a nested `report`
field containing the full output of `HealthMonitor.full_health_report()` (Day 27
module), wrapped in its own try/except so a report failure doesn't flip overall
service status to degraded. The original flat `status`/`services`/`counts` fields
are preserved unchanged for backward compatibility.

**Documented simplifications:**
- "Extraction success rate trend over time" (from the original plan) was not built.
  The corpus is frozen with no incremental ingestion, so no historical data points
  exist to chart — the current rate is shown as a single metric instead. In
  production, each health report would be timestamped and stored, enabling a real
  trend line. This is an honest scope reduction, not a missing feature — noted as
  an interview talking point.
- `HealthMonitor`'s optional `pipeline_status` (file freshness checks for raw
  `.jsonl` files on disk) was deliberately left disabled — `HealthMonitor(driver)`
  is called with no `data_dir` argument. No dashboard component consumes pipeline
  file status, and the correct path (`PROJECT_ROOT / "data" / "processed"`) is
  confirmed — enabling it later is a one-line change.
- `counts` (original Day 32 lightweight check) and `report.graph_size` (from
  HealthMonitor) report overlapping node/edge numbers in two different shapes.
  This is intentional: `counts` proves connectivity even if the fuller report
  fails, and both are kept for graceful degradation.