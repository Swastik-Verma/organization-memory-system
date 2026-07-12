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

Total files attempted:     517,401
Successfully parsed:       517,389
Failed to parse:           12
Success rate:              99.998%
Unique message_ids:        517,389
Duplicate records:         0
Records with valid date:   516,854
Records with null date:    535 (0.10%)
Earliest email date:       1997-01-01
Latest email date:         2005-12-29

---