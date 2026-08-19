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