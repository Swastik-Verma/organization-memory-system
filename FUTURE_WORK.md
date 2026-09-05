# Future Work / Extensions

Ideas for after the 60-day project is complete. Nothing here is scheduled, nothing here
blocks anything, and nothing here is a defect — these are deliberate scope boundaries and
"if I had more time" improvements, collected as they came up during the build.

**What this file is NOT:**
- Not a bug list. Known bugs and accepted limitations live in `CLAUDE.md` → Deferred Decisions.
- Not the remaining plan. Days 44–60 work is in `org_memory_system(Layer10)_full_plan.md`.
- Not scheduled performance work. Day 46 has its own performance/polish scope.

---

## 1. Entity Resolution — Merge System

### What was originally planned (written during Week 3 backend build)

The original design envisioned two major frontend features for Day 43:

1. **Fuzzy Merge Candidate Review UI** — the centerpiece feature. A card-by-card
   review interface for 2,503 below-threshold fuzzy candidates, showing side-by-side
   entity snapshots (aliases, emails, mentions for both source and target), with
   [Merge] [Skip] [Previous] [Next] navigation, sortable by confidence, filterable
   by strategy and entity type, searchable by name.

2. **Merge Audit Log** — a secondary table showing all completed merges (both Day 16
   automatic and Day 17/human-approved), with undo buttons on Day 17 merges only.

Five backend endpoints were specified:
- `GET /api/merges/candidates` — below-threshold candidates with full entity details
- `GET /api/merges/log` — combined Day 16 + Day 17 merge history
- `POST /api/merges/{source}/{target}` — execute a new merge
- `POST /api/merges/{merge_id}/undo` — reverse a merge using stored snapshots
- `POST /api/merges/candidates/{index}/skip` — mark candidate as reviewed-and-rejected

The undo flow was specified as 5 steps: find MergeOperation by ID, restore source
entity from snapshot, restore target entity from snapshot, restore resolution_map
entries on disk, mark status "undone."

A pipeline re-run note was documented: after human-approved merges change
`resolution_map.json`, Days 18–19 (claim dedup + conflict resolution) must be re-run
to pick up the improved entity resolution. Both scripts run in seconds.

### What actually got built

The data state had changed between when the plan was written and when Day 43 was
built. The plan assumed `auto_threshold: 1.0` (nothing auto-merges, all 2,503
candidates await human review). By build time, `auto_threshold` was `0.85` with
1,291 merges already applied and recorded in `merge_operations`. So the immediate
need shifted from "review unmerged candidates" to "audit already-applied merges."

The 60-day plan's Day 43 description also emphasized the audit log over the candidate
queue: "Filterable table of every entity merge showing date, both entities, reason,
confidence, trigger source, and status / Undo button / Reversed merges shown
distinctly."

**Built and working:**
- Merge audit log table — 3,315 rows (2,024 exact + 1,291 fuzzy), with columns for
  source entity, target entity, strategy, confidence, phase badge (Exact/Fuzzy),
  status badge (Active/Undone), date, and action (undo button). Filterable by phase,
  status, and strategy. Client-side search by entity name with debounced input and
  React.memo() optimization (search keystroke lag fixed: ~60ms → ~2ms per keystroke).
  Sortable columns. Actually exceeded the original spec which didn't mention filtering,
  sorting, search, or performance optimization.
- `GET /api/merges` — combined Day 16 + Day 17 merge list (same data as planned
  `GET /api/merges/log`, different URL)
- `POST /api/merges/{merge_id}/undo` — reverses a Day 17 fuzzy merge. Implements
  4 of the 5 planned undo steps (see gap below).
- Undo confirmation dialog explaining that claims are NOT reassigned.
- Day 16 exact merges shown as read-only rows (no undo button) — correct, since
  they have no snapshots; "undo" = re-run the script.

### Summary table

| Feature | Original Plan | What We Built | Status |
|---|---|---|---|
| Candidate review UI (2,503 items) | ✅ Core feature | ❌ Not built | Extension (§1.6) |
| Merge audit log | ✅ Basic table | ✅ Enhanced (filters, search, sort, badges) | Exceeded spec |
| Side-by-side entity detail | ✅ Full card layout | ❌ Names only | Day 46 backlog |
| Undo merges | ✅ Full 5-step | ✅ 4 of 5 steps | Resolution map gap (§1.8) |
| Execute new merge | ✅ Endpoint planned | ❌ Not built | Extension (§1.6) |
| Skip/reject candidate | ✅ Endpoint planned | ❌ Not built | Tied to candidate review UI |
| Pipeline re-run note | ✅ Documented | ❌ Not surfaced | Only matters once merge-approval exists |
| Entity type filter | ✅ Planned | ❌ Not built | Minor gap |
| Claim reassignment on undo | Not in original plan | Not built | Extension (§1.9) |
| Search debounce + memo | Not in original plan | ✅ Built (Claude Code fix) | Exceeded spec |

### What remains as extensions

#### 1.6 Fuzzy merge candidate review UI
2,503 below-threshold candidates in `entity_resolution_fuzzy.json` →
`below_threshold_candidates` have never been reviewed. Some are genuinely risky
("Jan Wilson" → "Jane Wilson", "Carl Carter" → "Carol Carter"), some are certainly
correct (0.99 confidence). The original plan's side-by-side card layout with
[Merge] [Skip] [Previous] [Next] navigation was the right design — show both
entities' full details (aliases, emails, mentions) so a reviewer can make an
informed decision. Would need three new backend endpoints: one to serve candidates
with full entity details, one to execute a merge (reusing `FuzzyMatcher.apply_merges()`
machinery), and one to mark a candidate as reviewed-and-skipped. Full day's work.

#### 1.7 Manual merge creation UI
Currently the system can only undo merges the pipeline already made — there is no
way for a human to select two arbitrary entities and merge them deliberately. All
the machinery exists (snapshot capture, alias/email union, mention_count combination)
from the Day 43 undo work; it would just need to be triggered manually instead of
by the fuzzy matcher. Naturally pairs with the candidate review UI (§1.6) since
both need the same "execute merge" endpoint, and with a redo/re-merge endpoint
(currently the only way to re-apply an undone merge is re-running
`batch_fuzzy_resolution.py`, which reprocesses everything).

#### 1.8 Undo doesn't update resolution_map.json
The undo endpoint restores entity identity in Neo4j and marks the merge operation
as "undone" in the JSON file, but does NOT reverse the corresponding entries in
`resolution_map.json`. After a merge of "Rick Causey" into "Richard Causey," the
resolution map says `"Rick Causey" → "person:causey-richard:..."` — undo restores
both Neo4j nodes but leaves this stale mapping on disk. Doesn't matter today (the
resolution map is only read when pipeline scripts are re-run, which isn't happening
after individual undos). Would matter if the pipeline were ever re-run after an
undo — the stale map would silently re-merge the entity that was just undone.

#### 1.9 Claim reassignment on merge undo
Undo restores entity identity (names, aliases, emails, mention counts) but does
NOT reassign claims — they keep whatever `subject_id`/`object_id` they were given
during Week 3 claim dedup. The mapping of "which claims belonged to which pre-merge
identity" was never recorded, so this information does not exist to restore.

A speculative fix: each claim's evidence carries a `message_id` and a verbatim
quote, so it may be possible to re-derive provenance by checking which name variant
literally appeared in that specific source email. Unverified, non-trivial, and only
partially applicable (relationship claims whose evidence uses pronouns wouldn't
resolve). Would need its own investigation before committing to build.

#### 1.10 Fuzzy blocking misses cross-block pairs
Strategy 4 (general fuzzy) blocks candidates by last-name token, so entities whose
canonical names end in different words are never compared — e.g. "John Klauberg" vs
"John Klauber". Strategies 1–3 don't use blocking, so many such cases are still
caught in practice. A looser blocking scheme (n-gram, phonetic) would close the gap
at a cost in candidate volume.

#### 1.11 ID generation doesn't sanitize non-standard address formats
Day 16's canonical ID generation builds IDs directly from raw extracted addresses,
assuming a standard `name@domain.com` shape. Enron's corpus contains internal
Lotus Notes-style addresses (`Name/OU/Corp/ENRON`), which slip through as literal
IDs containing spaces and slashes — e.g.
`person:kenneth-lay:kenneth lay/corp/enron-at-enron`.

Confirmed case: an orphaned 1-mention "Kenneth Lay" duplicate exists alongside
the canonical 1,272-mention entity. It's correctly indexed and returned by
entity search, but clicking into its detail page 404s — the literal `/` in the
ID gets interpreted as a URL path separator, so the browser sends a truncated,
mangled fragment of the ID to the backend, which then correctly reports no
entity with that (wrong) ID.

Real impact is narrow — one single-mention orphan, not a systemic problem; the
canonical Kenneth Lay entity is unaffected and fully correct. Fix would need two
coordinated changes: address-format validation/normalization at Day 16
ID-generation time (reject or clean non-standard formats before slugifying),
plus defensive URL-encoding of entity IDs on the frontend as a safety net for
any similar case that slips through.

#### 1.12 Expandable detail panel before undo decisions
The merge audit table shows canonical names, strategy, and confidence — not enough
context to judge whether a merge was correct. Both `source_snapshot` and
`target_snapshot` (full aliases, emails, mention counts) already exist in the
backend and are read by the undo endpoint; they are simply not sent to the frontend
in the list response. An expandable row or side panel showing both snapshots
side-by-side would let a reviewer make an informed decision instead of guessing
from two names. (Also tracked for Day 46.)

#### 1.13 Source email not shown, so distinct merges look like duplicates
The table shows `source_name` only. When the same person existed as two separate
pre-merge entities under the same display name — e.g. two "Rick Causey" records,
one with `rick.causey@enron.com` and one with `rcausey@enron.com`, both merged
into "Richard Causey" — the rows look like an accidental duplicate even though
they are two legitimate, distinct merge events. Showing the source email alongside
the name would disambiguate.

---

## 2. Evidence Selection and Display

### 2.1 No real tiebreaker for "which evidence is linked"
Both `/api/conflict-groups` (`admin.py`) and `/api/entities/{id}/claims` (`entities.py`) pick
the evidence to link via `ORDER BY e.confidence DESC` with no secondary sort key. Verified
live: most evidence records backing a claim are tied at `confidence: 1.0` — a flat
extraction-time default, not a computed score — so ties are the norm, not an edge case.
With everything tied, Cypher does not guarantee stable ordering across query plans, Neo4j
versions, or re-runs, which makes the "linked" evidence effectively incidental rather than
deliberate.

Fix would be adding a real secondary sort (most recent, longest/most specific quote, verified
first) to both queries. Small change, but backend, and only worth doing if the choice is
meant to carry meaning.

### 2.2 Entity Claims tab discards evidence it already fetched
`entities.py` fetches up to 5 evidence records per claim (`LIMIT 5`), but
`ClaimCard.tsx` surfaces only the first one — no "+N more" indicator, no count. The other
up-to-4 records come over the wire on every entity page load and are thrown away. The
Conflicts page already has the "+N more" treatment; this would be the same pattern,
frontend-only, no backend change needed.

### 2.3 True evidence count is unknowable past 5 on the entity page
Because of that `LIMIT 5`, the entity page cannot know how many evidence records actually
exist once a claim has more than five — unlike the Conflicts page, whose `evidence_count`
comes from an uncapped `size()`. If "+N more" is ever added to the entity page (2.2), the
count must come from a real backend `evidence_count` field, not `evidence.length`, or it
will silently under-report for well-supported claims.

---

## 3. Merge Audit Log

### 3.1 Source email not shown, so distinct merges look like duplicates
The table shows `source_name` only. When the same person existed as two separate pre-merge
entities under the same display name — e.g. two "Rick Causey" records, one with
`rick.causey@enron.com` and one with `rcausey@enron.com`, both merged into "Richard Causey" —
the rows look like an accidental duplicate even though they are two legitimate, distinct merge
events. Showing the source email alongside the name would disambiguate.

### 3.2 Expandable detail panel before undo decisions
The table shows canonical names, strategy, and confidence — not enough context to judge
whether a merge was correct. Both `source_snapshot` and `target_snapshot` (full aliases,
emails, mention counts) already exist in the backend and are read by the undo endpoint; they
are simply not sent to the frontend in the list response. An expandable row or side panel
showing both snapshots side-by-side would let a reviewer make an informed decision instead of
guessing from two names.

*(Also tracked for Day 46 — listed here in case it doesn't land there.)*

---

## 4. Conflict Review

### 4.1 Undo auto-resolution
Reversing a temporal succession chain — resetting each claim's `status`, `valid_to`,
`supersedes`, `superseded_by`, and recreating the removed `CONFLICTS_WITH` edges. Meaningfully
more complex than the merge undo, and only useful once 4.1 exists to surface the chains in the
first place.

Would require a `POST /api/conflict-resolutions/{conflict_id}/undo` endpoint that
reverses the auto-resolution for a single conflict group — not built, deferred until
the auto-resolved view (4.1) exists to trigger it from.

### 4.2 60 flagged decision reversals never reviewed
`decision_reversals.json` holds 60 decisions flagged by keyword scan ("no longer", "cancelled",
"reversed", "instead of", …). Known false-positive rate — "instead of" fires on ordinary
scheduling language. Deliberately, reversals are **not** linked to the specific decision they
reverse: that would require semantic matching across 12,331 decisions (O(n²) embedding
comparisons). Detection was built; linking and human review were deferred and never picked up.

### 4.4 Per-date-group resolution with temporal chaining
The current resolve UI treats all claims in a conflict group as one flat contest — "pick
one winner out of N." But multi-date conflicts like Brent Price (4 claims across 2 dates:
Mar 21 and Aug 16) actually contain two separate problems bundled together:
- Same-date ties (Mar 21: Sally Beck vs Fearnley Dyson) — a real ambiguity needing a
  human pick
- Cross-date succession (Mar 21 → Aug 16) — not ambiguous at all, just time passing

The fix would restructure each conflict card into per-date-group resolution blocks: one
pick per date that has a tie, with cross-date ordering handled automatically by chaining
`valid_to` values (each winner's `valid_to` = the next date group's `valid_from`, last
winner keeps `valid_to = null`). A card would only count as fully "Resolved" once every
internal date group is resolved, with a partial state ("2 of 3 groups resolved") shown
in between.

Open design decisions for when this is built:
- Losing claims within a same-date tie: recommended `valid_to = valid_from` (zero-length
  window, honestly encoding "superseded immediately, never established as current") vs
  leaving `valid_to = null` with just `status = superseded`
- The `resolution` field would need a third value (`"partially_resolved"`) beyond
  `needs_review` / `resolved` / `dismissed`
- Single-date claims with no tie (e.g. Harold Inman at Feb 17, alone at that date)
  need no human pick — they're just links in the temporal chain, resolved automatically
  once their neighboring date groups are decided

This mirrors the Day 19 auto-resolution logic for temporal succession but applied
interactively through the UI rather than as a batch script.

---

## 5. Security and Access Control

### 5.1 Real authentication
`get_current_user()` reads an `X-User-Clearance` header, maps `"1"`–`"4"` through a hardcoded
`DEMO_USERS` dict, and **defaults to clearance 4 when the header is absent**. Anyone can send
clearance 4. This exists to prove clearance flows correctly into
`retrieval_engine.retrieve(plan, user_clearance=...)` and is enforced at the Cypher level —
not to be secure.

The production path is already rehearsed: a users table with bcrypt-hashed passwords, a
`POST /api/auth/login` issuing a signed JWT carrying `sub`/`clearance`/`exp`, and replacing the
body of `get_current_user()` with `jwt.decode(...)`. **Every other route stays unchanged**,
because they all receive `CurrentUser` through FastAPI dependency injection — the whole point
of having built it that way.

### 5.2 Access classification uses keyword heuristics
Content is classified into the four clearance levels by keyword matching. This misses
sensitive content with no explicit marker — "We moved $50M to the offshore entity" contains no
confidentiality keyword and would be classified PUBLIC. Production would use source-system
labels (Microsoft Purview, Google DLP, email sensitivity flags) or a trained classifier. The
filtering architecture downstream stays identical either way.

---

## 6. Configuration and Operations

### 6.1 Confidence decay parameters are hardcoded
`DECAY_RATE_PER_YEAR`, `ARCHIVE_THRESHOLD`, and `MINIMUM_AGE_DAYS` are module-level constants.
In production these belong in a config store behind a protected admin endpoint so they can be
tuned without a code deploy.

### 6.2 Decay and drift detection are built but not applied
The Day 25 incremental update system (idempotency, supersession, confidence decay, ontology
drift detection) is implemented and tested, but **deliberately not run against the project
graph** — the Enron corpus ends in late 2001, so decay would archive perfectly valid claims
with no new emails arriving to replenish confidence. The code demonstrates the architecture;
exercising it would need a live, growing corpus.

### 6.3 Scheduled ingestion never wired up
APScheduler and an ingest-trigger endpoint were in the original tech-stack plan for scheduled
incremental update cycles. Never built — the corpus is frozen, so there was nothing to
schedule. Would become necessary the moment new mail starts arriving.

### 6.4 Health report is computed synchronously on every request
`HealthMonitor.full_health_report()` runs ~15 sequential Cypher aggregations across 56k nodes
and 122k edges per call, costing 8–13 seconds. On a frozen corpus the result never changes
between requests, so caching would eliminate it entirely; with live ingestion, a TTL cache or
async precomputation would be the right shape.

*(Parallelising these queries is tracked for Day 46; the caching angle belongs here.)*

### 6.5 Merge and conflict status live in JSON files, not the database
`/api/merges/{id}/undo` and `/api/conflict-groups/{id}/resolve` both rewrite multi-megabyte
JSON files on disk to record status changes. Fine for a single-user portfolio project; in
production this state belongs in the database, with the file kept as an immutable pipeline
artifact.

---

## 7. Data Pipeline

### 7.1 Email `To:` field never extracted
`Message` nodes carry `from_addr` but no `to_addr` — the raw `.eml` files have it, the Week 1
parser never pulled it out. Fixing it means re-running full ingestion. Accepted as a known
gap; recorded here because it's the kind of thing that looks like an oversight if
undocumented.

### 7.2 Evidence requirements only on relationship extraction
The extraction prompt requires verbatim evidence quotes for relationships but not for other
extracted fields. This was a deliberate design choice — relationships are the most
hallucination-prone type and benefit most from grounding. If rebuilding from scratch, evidence
requirements would be extended to all extracted fields.

### 7.3 Manual extraction evaluation never run
`backend/scripts/evaluate_extractions.py` is written and ready — an interactive script that
shows each source email alongside its extraction and prompts for a correct/partial/hallucinated
score. Deferred for time; automated failure analysis (`failure_analysis.json`) served as the
interim substitute. Needs 30–60 minutes of manual scoring to produce real precision numbers.

### 7.4 Qdrant deletion integration
`is_deleted` flags exist on evidence and ingestion skips flagged records, but there is no path
that removes the corresponding vectors from Qdrant when something is deleted after indexing.
A deletion endpoint would need to clear both stores to stay consistent.

### 7.5 96 claims without SUBJECT edge, 22 without OBJECT
Some `subject_id`/`object_id` values point at Organization IDs (e.g. "Enron informs Kenneth
Lay"), but the SUBJECT/OBJECT Cypher in the loader only matches `:Person` nodes. Extending
the match to cover `:Organization` would close the gap. Documented rather than fixed to keep
the Day 35 baseline stable.

---

## 8. Retrieval and Chat

### 8.1 N+1 query on the claims endpoint
`/api/entities/{id}/claims` fires one extra Cypher round-trip per claim to fetch evidence —
measured at 1.24s for an entity with 247 claims. Scales linearly with claim count. Fixable by
batching all evidence into a single `OPTIONAL MATCH` across the claim set. Accepted as a known
tradeoff for demo scale.

### 8.2 Streaming chat responses
Each question costs ~8–9 seconds: two Gemini API round-trips (query parsing, answer
generation) plus hybrid graph and vector retrieval. The latency is API-bound rather than
compute-bound, so it can't be optimised away — but streaming the answer token-by-token would
make it *feel* far faster, which is what actually matters for a chat interface.

### 8.3 "Who reports TO X?" reverse queries
Temporal queries answer "who does X report to". The reverse direction needs
`get_relationships_involving()` or a dedicated method; noted during Week 4 as something the
chatbot would eventually surface a need for.

---

## 9. Frontend Polish

### 9.1 Bundle size
The production build emits a single ~943 kB JS chunk (~288 kB gzipped), over Vite's 500 kB
advisory threshold. Expected given Recharts, react-force-graph-2d, and a full component
library, and harmless at demo scale. Route-level code splitting via dynamic `import()` would
bring it down.

### 9.2 Graph node radius caps at 20
Entities above roughly 150 mentions all render at identical size, so the visual difference
between a 200-mention and a 2,240-mention entity is lost. **Explicitly left as-is by
decision** — recorded here only so it isn't mistaken for a bug and "fixed" by someone later.

---

## 10. Deployment

### 10.1 Live public deployment
Day 56 in the original plan covers deploying backend to Railway and frontend to Vercel for a
live public link. Listed here because if the project stops before Day 56, this is the single
highest-value remaining item for a portfolio — a working link beats a repo for most reviewers.