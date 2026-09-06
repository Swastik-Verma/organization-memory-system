# Known Issues

Consolidated, severity-ranked list of all known defects and behavioural issues in the
Organizational Memory System, compiled during the Day 48 end-to-end integration test.

**What this file is:** actual defects — things that are currently wrong, behave
unexpectedly, or are untested enough that correctness can't be claimed.

**What this file is NOT:**
- Not a feature backlog. Unbuilt features and "if I had more time" extensions live in
  `FUTURE_WORK.md`.
- Not a decisions log. Design rationale and standing instructions live in `CLAUDE.md`
  → Deferred Decisions.

Where an issue is also tracked elsewhere, this file cross-references rather than
duplicating the full write-up.

**Last updated:** Day 48
**Testing basis:** full stack running via `docker compose up -d` (Neo4j, Qdrant,
FastAPI backend, nginx-served React frontend), systematic click-through of all
pages and flows.

---

## Severity definitions

| Level | Meaning |
|---|---|
| **Critical** | Produces incorrect results, corrupts data, or breaks a feature entirely. Would block a production release. |
| **High** | Significantly degrades a major feature, or leaves a primary feature's correctness unverified. Should be fixed before real-world use. |
| **Medium** | Affects a specific workflow or edge case. Noticeable, but core functionality still works. |
| **Low** | Cosmetic, minor, or an accepted performance tradeoff. Safe to ship as-is. |

---

## Critical

**None identified.**

Day 48 testing found no issue that produces incorrect data, corrupts state, or
breaks a feature outright. All six pages load, all endpoints respond, and the
numbers shown match the recorded Day 27 baseline (quality score 97.9, average
confidence 0.9504, evidence verification 96.7%, 8,595 messages, 5,586 claims).

---

## High

### H1 — Chatbot has never had a systematic correctness pass
**Where:** `backend/src/chatbot/`, `POST /api/chat`
**Status:** open, highest-priority item in the project

The chatbot is the system's primary user-facing feature and the one most likely to
be exercised in a demo or interview, yet its behaviour has only ever been spot-checked.
Untested or barely-tested areas include: Deal and Decision entity types, ambiguous
name handling, multi-turn follow-ups, questions with no good answer in the corpus,
and questions that span multiple claim types.

Day 48 testing found no *new* failure here — simple questions, relationship queries,
temporal queries, no-answer cases and citation click-through all behaved correctly.
That is reassuring but not sufficient: the absence of failure across a handful of
manual questions is not evidence of correctness across the space of possible ones.

This is rated High not because a specific thing is known to be broken, but because
the correctness of the headline feature is currently *unverified* rather than
*verified*.

**Fix:** a dedicated debugging session (or several), driven by a written matrix of
question types × entity types × edge cases, not ad-hoc questioning.
**Cross-reference:** `CLAUDE.md` → Deferred Decisions → Open backlog, item 1.

### H2 — Clarification loop never resolves to an answer
**Where:** Day 33–34 clarification logic, `POST /api/chat`
**Status:** open, reproducible historically

Ambiguous queries produce clarification options that are themselves malformed —
observed case: "Who does Sally Beck report to?" generating "Fernley Dyson and Sally
Beck" as a *single* candidate option. Selecting an option re-triggers clarification
instead of resolving, so the conversation never reaches an answer.

Two distinct defects are bundled here: (a) option generation/deduplication produces
garbled candidates, and (b) selecting an option fails to resolve the ambiguity it
was meant to resolve. Week 8 entity-resolution work may reduce how often (a) triggers
but will not fix (b).

Not reproduced during Day 48 testing (the questions asked happened not to trigger
clarification), which does not clear it — it means the trigger conditions are
narrower than the failure is severe.

**Cross-reference:** `CLAUDE.md` → Deferred Decisions → Open backlog, item 2.

---

## Medium

### M1 — Evidence quote highlighting is broken on real email bodies
**Where:** `SourceEmail.tsx` → `renderBody()`, evidence detail page
**Status:** CONFIRMED BROKEN — verified against live data on Day 42, not fixed

The evidence quote is not highlighted inside the source email body. `SourceEmail.tsx`
uses a plain `email_body.includes(quote)` check, unchanged since Day 40 — no whitespace
normalization was ever added.

Verified empirically rather than by code inspection: Sally Beck's 247 claims were pulled
from `/api/entities/{id}/claims`, real evidence fetched via `/api/evidence/{evidence_id}`
for the first 8 claims that had any, and each quote tested against its body.
**5 of 8 failed the plain `includes()` check. All 8 passed once both strings were
normalized by collapsing whitespace** (`quote.split(/\s+/).join(' ')`). That confirms
the failure is specifically the `\n`-vs-space mismatch — LLM-extracted quotes normalize
whitespace, raw stored bodies preserve hard line breaks — and not some other class of
mismatch.

A ~60% failure rate on a feature whose entire purpose is showing *where* a claim came
from is a meaningful gap in the evidence-trail story, which is the system's core premise.

**Fix:** normalize both `quote` and `email_body` identically before the `includes`/`split`
call, but render the highlight against the *original* unnormalized body — `SourceEmail`
displays the raw body verbatim in a `<pre>`, so highlighting a mangled copy would visibly
alter the email text.
**Cross-reference:** `CLAUDE.md` → Deferred Decisions → Evidence quote highlighting;
`docs/PROJECT_CONTEXT_Day36-onward.md` → Day 42 → Step 6.

### M2 — Orphaned entity with malformed ID returns 404 on click
**Where:** Day 16 canonical ID generation; entity detail route
**Status:** confirmed, reproducible

Enron's corpus contains Lotus Notes-style internal addresses (`Name/OU/Corp/ENRON`)
which Day 16 slugified verbatim, producing IDs containing literal spaces and slashes
— e.g. `person:kenneth-lay:kenneth lay/corp/enron-at-enron`.

Reproducible: search "Kenneth Lay" on `/entities`, two results appear (1,272 mentions
and 1 mention). The 1-mention duplicate is correctly indexed and returned by search,
but clicking it 404s — the literal `/` is parsed as a URL path separator, so a
truncated ID fragment reaches the backend, which correctly reports no such entity.

Impact is narrow: one single-mention orphan. The canonical Kenneth Lay entity is
complete and unaffected. But it is a genuine dead end in the UI, not a cosmetic
issue, hence Medium rather than Low.

**Fix:** address-format validation at ID-generation time, plus defensive URL-encoding
of entity IDs on the frontend as a safety net.
**Cross-reference:** `FUTURE_WORK.md` §1.11.

### M3 — Citation numbers appear out of sequential order
**Where:** Chat answer rendering
**Status:** confirmed, cosmetic but user-visible

Citation markers in a chat answer appear non-sequentially (e.g. 14, 6, 10, 5, 2…).
Every marker still links to the correct evidence, so nothing is functionally wrong —
but it looks like a bug to anyone reading the answer, which matters for a
demo-facing feature.

**Fix:** renumber citations by order of first appearance in the answer text.
**Cross-reference:** `CLAUDE.md` → Deferred Decisions → Open backlog, item 3.

### M4 — Which evidence gets linked per claim is effectively arbitrary
**Where:** `admin.py` (`/api/conflict-groups`), `entities.py` (`/api/entities/{id}/claims`)
**Status:** confirmed by live inspection

Both endpoints select the evidence to surface via `ORDER BY e.confidence DESC` with
no secondary sort key. Verified live: evidence records backing a single claim are
routinely all tied at `confidence: 1.0`, because confidence is a flat extraction-time
default rather than a computed score. With every candidate tied, Cypher provides no
ordering guarantee — the "chosen" evidence is whatever the storage scan happens to
return first, and is not stable across query plans, Neo4j versions, or re-runs.

Rated Medium rather than Low because the evidence shown is the system's justification
for a claim; showing an arbitrary one undermines the "full evidence trail" premise
even though every candidate is individually valid.

**Fix:** add a real secondary sort (most recent, longest/most specific quote,
verified-first) to both queries.
**Cross-reference:** `FUTURE_WORK.md` §2.1.

---

## Low

### L1 — Merge table column headers drift out of alignment on narrow viewports
**Where:** `/merges`, virtualized table (Day 46)
**Status:** newly found during Day 48 testing

At full width the merge audit table renders correctly. When the browser window is
narrowed, the table body scrolls horizontally as intended, but the column header row
does not stay aligned with the body columns during that scroll and overflows outside
the container.

CSS issue only — header and body need to share a single horizontal scroll context.
No data is wrong, and the table is fully usable at normal window widths.

### L2 — Timeline ordering is non-deterministic among same-date claims
**Where:** `/api/entities/{id}/timeline`
**Status:** newly identified during Day 48 testing

The timeline query orders by `valid_from` with no secondary sort key. Claims sharing
the same date therefore appear in whatever order Neo4j returns them, which is not
guaranteed stable across runs. All same-date claims do appear grouped together
correctly — only their order *within* the tie is arbitrary.

Same root cause as M4 (no tiebreaker on an ordering query), but lower impact:
the grouping is still correct and no single item is being privileged over others.

### L3 — N+1 query pattern on the claims endpoint
**Where:** `/api/entities/{id}/claims`
**Status:** known, accepted tradeoff

One additional Cypher round-trip per claim to fetch its evidence. Measured at 1.24s
for an entity with 247 claims; scales linearly with claim count.

**Fix:** batch all evidence into a single `OPTIONAL MATCH` across the claim set.
**Cross-reference:** `CLAUDE.md` → Deferred Decisions → Open backlog, item 4;
`FUTURE_WORK.md` §8.1.

### L4 — Health dashboard takes 8–13 seconds to load
**Where:** `HealthMonitor.full_health_report()` via `GET /api/health`
**Status:** known, deliberately deferred

~15 Cypher aggregation queries run sequentially in a single session. The cost is
accumulated round-trip time, not per-query computation. Impact is bounded because
the page fetches once on load with no auto-polling, and the corpus is frozen so the
result never changes between requests.

**Fix:** parallel execution (async driver or thread pool), or caching, given the
data is static.
**Cross-reference:** `FUTURE_WORK.md` §6.4 and §6.6.

### L5 — Entity Claims tab fetches 5 evidence records per claim and shows 1
**Where:** `entities.py` (`LIMIT 5`), `ClaimCard.tsx`
**Status:** known

Up to four evidence records per claim are fetched over the wire on every entity page
load and then discarded — no "+N more" indicator, no count. The Conflicts page
already implements exactly this affordance, so the pattern exists and could be
mirrored with no backend change.

Related: because of the `LIMIT 5` cap, the entity page cannot know the true evidence
count once a claim has more than five. If "+N more" is added, the count must come
from a real backend `evidence_count` field, not `evidence.length`, or it will
silently under-report.

**Cross-reference:** `FUTURE_WORK.md` §2.2, §2.3.

### L6 — Production bundle exceeds Vite's size advisory
**Where:** `frontend/` build output
**Status:** known, harmless at current scale

A single ~943 kB JS chunk (~288 kB gzipped), over Vite's 500 kB warning threshold.
Expected given Recharts, react-force-graph-2d and a full component library. Load
times are acceptable locally; would matter more on a slow public connection.

**Fix:** route-level code splitting via dynamic `import()`.
**Cross-reference:** `FUTURE_WORK.md` §9.1.

---

## Not Bugs — Documented Limitations

These behave as designed. They are recorded here specifically so they are not
mistaken for defects and "fixed" by someone unfamiliar with the reasoning.

### Data model and pipeline

- **Merge undo does not reassign claims.** Claim dedup (Day 18) runs *after* entity
  resolution (Days 16–17) and consumes its output, rewriting each claim's
  subject/object to a final canonical ID. Which pre-merge identity produced a given
  claim is discarded at that point, so undo has nothing to split claims back apart
  by. A possible structural recovery path exists — see `FUTURE_WORK.md` §1.9.
- **Day 16 exact merges have no undo button.** They carry no snapshots because they
  are fully deterministic; "undo" means re-running the resolution script with
  different rules, not a UI action.
- **Email `To:` field is absent.** `Message` nodes have `from_addr` but no
  `to_addr` — the raw `.eml` files contain it, the Week 1 parser never extracted it.
  Fixing requires full re-ingestion.
- **96 claims have no SUBJECT edge, 22 have no OBJECT edge.** Some subject/object IDs
  point at Organizations (e.g. "Enron informs Kenneth Lay") but the loader's Cypher
  only matches `:Person`. Left as-is to keep the Day 35 baseline stable.
  See `FUTURE_WORK.md` §7.5.

### Counts that look inconsistent but aren't

- **Health dashboard shows 25,034 entities; the Entities page shows 21,731.** The
  dashboard counts Person + Organization + Deal; the Entities page counts only
  Person + Organization, because Deals have no entity detail page (they are reachable
  via the Graph Explorer). The ~3,300 difference is exactly the Deal count.
- **Health dashboard shows 25 conflict pairs; the Conflicts page shows 14 groups.**
  Both are correct: 14 grouped conflicts contain 33 individual participating claims,
  and a group of *n* mutually-conflicting claims contributes C(n,2) edge pairs — 25
  in total across all groups.
- **Confidence distribution histogram shows only 2 bars.** The corpus minimum claim
  confidence is 0.7, so the `0.50–0.69`, `0.30–0.49` and `0.00–0.29` buckets are
  genuinely absent from the data (not zero-valued — absent as keys).
- **Global search group counts cap at 10 per type.** `/api/search` returns at most
  `PER_TYPE_LIMIT` (10) results per node type, so a group header reads "how many are
  shown", not the true total. Deliberate: this is a search *preview*; the dedicated
  pages exist for exhaustive browsing.

### Deliberate scope decisions

- **All conflicts are `reports_to` type.** Day 18 restricted conflict detection to
  `EXCLUSIVE_TYPES = {"reports_to"}`; the other four claim types legitimately permit
  multiple simultaneous objects, so multiple objects is normal there, not a conflict.
- **Health dashboard has no "extraction success rate over time" chart.** The corpus
  is frozen with no incremental ingestion, so no historical data points exist to plot.
  Current rate is shown as a single metric instead.
- **`HealthMonitor.pipeline_status` is disabled.** `HealthMonitor(driver)` is
  constructed with no `data_dir`, so file-freshness checks are omitted — no dashboard
  component consumes them. One-line change if ever needed.
- **`/api/health` returns overlapping counts in `counts` and `report.graph_size`.**
  Intentional: `counts` comes from the lightweight Day 32 connectivity check and
  still populates if the fuller Day 27 report fails, giving graceful degradation.
- **Graph node radius caps at 20.** Entities above ~150 mentions all render at the
  same size. Explicit Day 38 decision, explicitly not to be changed.
- **Day 34 follow-up resolver limitations are accepted.** Missed bare pronouns, false
  positives, wrong referents and the hard 5-turn cutoff are documented interview
  talking points. The proposed "Rule 6 escape hatch" fix was explicitly declined —
  do not implement without being asked.
- **Authentication is deliberately not production-secure.** `get_current_user()`
  reads an `X-User-Clearance` header against a hardcoded demo dict and defaults to
  clearance 4 when absent. It exists to prove clearance propagates correctly into
  Cypher-level filtering. The JWT replacement path is designed and documented in
  `FUTURE_WORK.md` §5.1 — every other route stays unchanged because they all receive
  `CurrentUser` via dependency injection.

---

## Test coverage note

Day 48 exercised the running system end-to-end through Docker: health dashboard,
chat (simple / relationship / temporal / ambiguous / no-answer / follow-up /
citation click-through), entity list and detail, graph explorer, merge audit log
(filters, search, expandable detail panel, scroll performance), conflict review
(both tabs), global search (all filter combinations), cross-page consistency, SPA
routing on hard refresh, and backend-down error states.

Not exercised: re-running the ingestion pipeline from raw `.eml` files inside
containers. The batch scripts under `backend/scripts/` were never containerised —
Day 47 containerised the serving layer (FastAPI + frontend) only. The corpus is
frozen by design, so a re-run would re-spend Gemini API quota to reproduce data
that already exists.