"""
Day 23 — Graph Loader

Reads the four canonical data files from Weeks 2-3 and loads everything
into Neo4j using idempotent MERGE operations.

Loading order (dependency-driven):
  1. Person + Organization nodes
  2. Message nodes
  3. Deal + Decision nodes
  4. Claim + Evidence nodes
  5. All edges

Source files:
  - entity_resolution_fuzzy.json  → Person, Organization
  - extraction_subset.jsonl       → Message (minus duplicate_ids.json)
  - extractions_final.jsonl       → Deal, Decision
  - resolved_claims.jsonl         → Claim, Evidence

Design decisions:
  - MERGE (not CREATE) on every write → idempotent, safe to re-run
  - UNWIND $batch pattern → batch loading, ~500 items per transaction
  - Resolution at load time → affects, made_by, sent_by all resolved via
    resolution_map.json + email index built from entity data
  - org_type normalized at load time via ORG_TYPE_MAP
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase, Session

from src.graph.schema import normalize_org_type


# ============================================================
# HELPERS
# ============================================================

BATCH_SIZE = 500


def _sha256_short(text: str, length: int = 16) -> str:
    """SHA-256 hash truncated to `length` hex chars."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _slugify(name: str) -> str:
    """Convert a name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    return slug


def _make_deal_id(name: str) -> str:
    return f"deal:{_slugify(name)}"


def _make_decision_id(message_id: str, description: str) -> str:
    return f"decision:{_sha256_short(message_id + description)}"


def _make_evidence_id(message_id: str, quote: str) -> str:
    return f"evidence:{_sha256_short(message_id + quote)}"


def _run_in_batches(session: Session, cypher: str, items: list[dict], batch_size: int = BATCH_SIZE) -> int:
    """
    Run a Cypher UNWIND query in batches.
    Returns total items processed.
    """
    total = 0
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        session.run(cypher, batch=batch)
        total += len(batch)
    return total


# ============================================================
# GRAPH LOADER
# ============================================================

class GraphLoader:
    """
    Loads all data files into Neo4j.

    Usage:
        loader = GraphLoader(driver, data_dir)
        stats = loader.load_all()
    """

    def __init__(self, driver, data_dir: Path):
        self.driver = driver
        self.data_dir = data_dir
        self.stats: dict[str, int] = {}

        # Built during loading — maps email addresses to canonical person IDs
        # Used for SENT_BY / SENT_TO edges
        self._email_to_person_id: dict[str, str] = {}

        # Resolution map — maps name strings to canonical entity IDs
        # Used for MADE_BY, AFFECTS, PARTY
        self._resolution_map: dict[str, str] = {}

        # Duplicate message IDs to skip
        self._duplicate_ids: set[str] = set()

    # ----------------------------------------------------------
    # PUBLIC API
    # ----------------------------------------------------------

    def load_all(self) -> dict[str, int]:
        """
        Load everything in dependency order.
        Returns a stats dict with counts for each phase.
        """
        self._load_lookups()

        with self.driver.session() as session:
            # Phase 1: Nodes (dependency order)
            print("\n=== Phase 1: Loading nodes ===")
            self._load_persons(session)
            self._load_organizations(session)
            self._load_messages(session)
            self._load_deals(session)
            self._load_decisions(session)
            self._load_claims_and_evidence(session)

            # Phase 2: Edges
            print("\n=== Phase 2: Creating edges ===")
            self._create_claim_subject_object_edges(session)
            self._create_evidence_message_edges(session)
            self._create_message_sender_edges(session)
            self._create_message_recipient_edges(session)
            self._create_decision_made_by_edges(session)
            self._create_decision_affects_edges(session)
            self._create_deal_party_edges(session)
            self._create_supersedes_edges(session)
            self._create_conflicts_with_edges(session)

        return self.stats

    # ----------------------------------------------------------
    # LOOKUP DATA (loaded once, used throughout)
    # ----------------------------------------------------------

    def _load_lookups(self):
        """Load resolution map and duplicate IDs into memory."""
        print("Loading lookup data...")

        # Resolution map: name string → canonical entity ID
        map_path = self.data_dir / "resolution_map.json"
        if map_path.exists():
            self._resolution_map = json.loads(map_path.read_text())
            print(f"  Resolution map: {len(self._resolution_map):,} entries")
        else:
            print("  WARNING: resolution_map.json not found — name resolution disabled")

        # Duplicate IDs to skip
        dup_path = self.data_dir / "duplicate_ids.json"
        if dup_path.exists():
            self._duplicate_ids = set(json.loads(dup_path.read_text()))
            print(f"  Duplicate IDs: {len(self._duplicate_ids):,} to skip")
        else:
            print("  WARNING: duplicate_ids.json not found — no duplicates skipped")

    # ----------------------------------------------------------
    # PHASE 1: NODES
    # ----------------------------------------------------------

    def _load_persons(self, session: Session):
        """Load Person nodes from entity_resolution_fuzzy.json."""
        entities = self._read_canonical_entities()
        persons = []

        for eid, entity in entities.items():
            if entity.get("entity_type") != "person":
                continue
            persons.append({
                "id": entity["canonical_id"],
                "canonical_name": entity["canonical_name"],
                "aliases": entity.get("aliases", []),
                "emails": entity.get("emails", []),
                "mention_count": entity.get("mention_count", 0),
                "is_deleted": False,
            })

            # Build email → person_id reverse index for SENT_BY/SENT_TO
            for email in entity.get("emails", []):
                self._email_to_person_id[email.lower()] = entity["canonical_id"]

        cypher = """
        UNWIND $batch AS row
        MERGE (p:Person {id: row.id})
        SET p.canonical_name = row.canonical_name,
            p.aliases = row.aliases,
            p.emails = row.emails,
            p.mention_count = row.mention_count,
            p.is_deleted = row.is_deleted
        """
        count = _run_in_batches(session, cypher, persons)
        self.stats["persons"] = count
        print(f"  Persons: {count:,}")

    def _load_organizations(self, session: Session):
        """Load Organization nodes from entity_resolution_fuzzy.json."""
        entities = self._read_canonical_entities()
        orgs = []

        for eid, entity in entities.items():
            if entity.get("entity_type") != "organization":
                continue

            # Normalize org_type from 120+ free-text to 6 categories
            raw_org_type = entity.get("org_type")
            normalized = normalize_org_type(raw_org_type)
            org_type_str = normalized.value if normalized else None

            orgs.append({
                "id": entity["canonical_id"],
                "canonical_name": entity["canonical_name"],
                "aliases": entity.get("aliases", []),
                "emails": entity.get("emails", []),
                "mention_count": entity.get("mention_count", 0),
                "org_type": org_type_str,
                "is_deleted": False,
            })

        cypher = """
        UNWIND $batch AS row
        MERGE (o:Organization {id: row.id})
        SET o.canonical_name = row.canonical_name,
            o.aliases = row.aliases,
            o.emails = row.emails,
            o.mention_count = row.mention_count,
            o.org_type = row.org_type,
            o.is_deleted = row.is_deleted
        """
        count = _run_in_batches(session, cypher, orgs)
        self.stats["organizations"] = count
        print(f"  Organizations: {count:,}")

    def _load_messages(self, session: Session):
        """Load Message nodes from extraction_subset.jsonl, skipping duplicates."""
        subset_path = self.data_dir / "extraction_subset.jsonl"
        messages = []

        with open(subset_path) as f:
            for line in f:
                email = json.loads(line)
                mid = email["message_id"]

                # Skip duplicates identified in Day 15
                if mid in self._duplicate_ids:
                    continue

                # Extract date as string (YYYY-MM-DD) for consistent storage
                date_str = None
                if email.get("date"):
                    raw_date = str(email["date"])
                    # Handle both "2001-06-15" and "2001-06-15T..." formats
                    date_str = raw_date.split("T")[0] if "T" in raw_date else raw_date

                messages.append({
                    "message_id": mid,
                    "date": date_str,
                    "subject": email.get("subject"),
                    "from_addr": email.get("from_addr"),
                    "body": email.get("body"),
                    "x_origin": email.get("x_origin"),
                    "x_folder": email.get("x_folder"),
                    "is_deleted": False,
                })

        cypher = """
        UNWIND $batch AS row
        MERGE (m:Message {message_id: row.message_id})
        SET m.date = row.date,
            m.subject = row.subject,
            m.from_addr = row.from_addr,
            m.body = row.body,
            m.x_origin = row.x_origin,
            m.x_folder = row.x_folder,
            m.is_deleted = row.is_deleted
        """
        count = _run_in_batches(session, cypher, messages)
        self.stats["messages"] = count
        print(f"  Messages: {count:,} (skipped {len(self._duplicate_ids):,} duplicates)")

    def _load_deals(self, session: Session):
        """
        Load Deal nodes from extractions_final.jsonl.

        Multiple emails may mention the same deal by name. Since Deal ID
        is based on the slugified name, MERGE handles dedup automatically —
        same name = same ID = same node.
        """
        final_path = self.data_dir / "extractions_final.jsonl"
        seen_deal_ids: set[str] = set()
        deals = []
        deal_parties_raw: list[dict] = []

        with open(final_path) as f:
            for line in f:
                extraction = json.loads(line)
                message_id = extraction["message_id"]
                if message_id in self._duplicate_ids:
                    continue

                for deal in extraction.get("deals", []):
                    if deal.get("status") == "rejected":
                        continue

                    name = deal.get("name", "").strip()
                    if not name:
                        continue

                    deal_id = _make_deal_id(name)

                    # --- Resolve parties FIRST before the append ---
                    parties_resolved = []
                    parties_unresolved = []

                    for party_name in deal.get("parties_involved", []):
                        if not party_name or not party_name.strip():
                            continue
                        clean_name = party_name.strip()
                        canonical_id = self._resolution_map.get(clean_name)
                        if canonical_id:
                            parties_resolved.append({
                                "deal_id": deal_id,
                                "party_name": clean_name,
                                "entity_id": canonical_id,
                            })
                        else:
                            parties_unresolved.append(clean_name)

                    # Now parties_unresolved is defined — safe to append
                    if deal_id not in seen_deal_ids:
                        seen_deal_ids.add(deal_id)
                        deals.append({
                            "id": deal_id,
                            "name": name,
                            "deal_status": deal.get("status"),
                            "parties_unresolved": parties_unresolved,
                            "is_deleted": False,
                        })

                    # Accumulate resolved party edges regardless of whether
                    # this deal_id is new (same deal in multiple emails
                    # may have additional parties)
                    deal_parties_raw.extend(parties_resolved)

        self._deal_parties_raw = deal_parties_raw

        cypher = """
        UNWIND $batch AS row
        MERGE (d:Deal {id: row.id})
        SET d.name = row.name,
            d.status = row.deal_status,
            d.parties_unresolved = row.parties_unresolved,
            d.is_deleted = row.is_deleted
        """
        count = _run_in_batches(session, cypher, deals)
        self.stats["deals"] = count
        print(f"  Deals: {count:,}")

    def _load_decisions(self, session: Session):
        """
        Load Decision nodes from extractions_final.jsonl.

        Each decision gets a deterministic ID from sha256(message_id + description).
        The made_by and affects fields are stored temporarily and resolved
        into edges in Phase 2.
        """
        final_path = self.data_dir / "extractions_final.jsonl"
        seen_decision_ids: set[str] = set()
        decisions = []
        decision_edges_raw: list[dict] = []  # For MADE_BY and AFFECTS edges

        with open(final_path) as f:
            for line in f:
                extraction = json.loads(line)
                message_id = extraction["message_id"]
                if message_id in self._duplicate_ids:
                    continue

                for dec in extraction.get("decisions", []):
                    # Skip non-approved
                    if dec.get("status") == "rejected":
                        continue

                    description = dec.get("description", "").strip()
                    if not description:
                        continue

                    decision_id = _make_decision_id(message_id, description)

                    if decision_id not in seen_decision_ids:
                        seen_decision_ids.add(decision_id)

                        # Resolve affects: match → edge later, no match → text property
                        affects_list = dec.get("affects", [])
                        affects_resolved = []
                        affects_unresolved = []

                        for aff_str in affects_list:
                            if not aff_str or not aff_str.strip():
                                continue
                            aff_clean = aff_str.strip()
                            canonical_id = self._resolution_map.get(aff_clean)
                            if canonical_id:
                                affects_resolved.append({
                                    "decision_id": decision_id,
                                    "entity_id": canonical_id,
                                })
                            else:
                                affects_unresolved.append(aff_clean)

                        made_by_name = dec.get("made_by")
                        made_by_id = None
                        if made_by_name and made_by_name.strip():
                            made_by_id = self._resolution_map.get(made_by_name.strip())

                        decisions.append({
                            "id": decision_id,
                            "description": description,
                            "made_by_name": made_by_name,
                            "affects_unresolved": affects_unresolved,
                            "is_deleted": False,
                        })

                        # Store edge data for Phase 2
                        if made_by_id:
                            decision_edges_raw.append({
                                "decision_id": decision_id,
                                "person_id": made_by_id,
                                "edge_type": "MADE_BY",
                            })
                        for ar in affects_resolved:
                            decision_edges_raw.append({
                                "decision_id": ar["decision_id"],
                                "entity_id": ar["entity_id"],
                                "edge_type": "AFFECTS",
                            })

        # Store for edge creation phase
        self._decision_edges_raw = decision_edges_raw

        cypher = """
        UNWIND $batch AS row
        MERGE (d:Decision {id: row.id})
        SET d.description = row.description,
            d.made_by_name = row.made_by_name,
            d.affects_unresolved = row.affects_unresolved,
            d.is_deleted = row.is_deleted
        """
        count = _run_in_batches(session, cypher, decisions)
        self.stats["decisions"] = count
        print(f"  Decisions: {count:,}")

    def _load_claims_and_evidence(self, session: Session):
        """
        Load Claim and Evidence nodes from resolved_claims.jsonl.

        Each claim becomes a :Claim node. Each item in its evidence list
        becomes an :Evidence node. The SUPPORTED_BY edge is created here too
        (since evidence is embedded within the claim data).
        """
        claims_path = self.data_dir / "resolved_claims.jsonl"
        claims = []
        evidences = []
        supported_by_edges = []

        with open(claims_path) as f:
            for line in f:
                claim = json.loads(line)

                claims.append({
                    "id": claim["claim_id"],
                    "claim_type": claim["claim_type"],
                    "description": claim.get("description", ""),
                    "confidence": claim.get("confidence", 0.0),
                    "valid_from": claim.get("valid_from"),
                    "valid_to": claim.get("valid_to"),
                    "status": claim.get("status", "current"),
                    "mention_count": claim.get("mention_count", 1),
                    "subject_id": claim["subject_id"],
                    "object_id": claim["object_id"],
                    "subject_name": claim.get("subject_name"),
                    "object_name": claim.get("object_name"),
                    "supersedes": claim.get("supersedes"),
                    "superseded_by": claim.get("superseded_by"),
                    "conflicts_with": claim.get("conflicts_with", []),
                    "is_deleted": False,
                })

                # Process evidence items within this claim
                for ev in claim.get("evidence", []):
                    ev_message_id = ev.get("message_id", "")
                    ev_quote = ev.get("quote", "")

                    if not ev_quote:
                        continue

                    ev_id = _make_evidence_id(ev_message_id, ev_quote)

                    evidences.append({
                        "id": ev_id,
                        "quote": ev_quote,
                        "char_start": ev.get("char_start"),
                        "char_end": ev.get("char_end"),
                        "evidence_verified": ev.get("evidence_verified"),
                        "confidence": ev.get("confidence", 0.0),
                        "email_date": ev.get("email_date"),
                        "message_id": ev_message_id,
                        "is_deleted": False,
                    })

                    supported_by_edges.append({
                        "claim_id": claim["claim_id"],
                        "evidence_id": ev_id,
                    })

        # Store edges for Phase 2
        self._supported_by_edges = supported_by_edges

        # Load Claim nodes
        claim_cypher = """
        UNWIND $batch AS row
        MERGE (c:Claim {id: row.id})
        SET c.claim_type = row.claim_type,
            c.description = row.description,
            c.confidence = row.confidence,
            c.valid_from = row.valid_from,
            c.valid_to = row.valid_to,
            c.status = row.status,
            c.mention_count = row.mention_count,
            c.subject_id = row.subject_id,
            c.object_id = row.object_id,
            c.subject_name = row.subject_name,
            c.object_name = row.object_name,
            c.supersedes = row.supersedes,
            c.superseded_by = row.superseded_by,
            c.conflicts_with = row.conflicts_with,
            c.is_deleted = row.is_deleted
        """
        claim_count = _run_in_batches(session, claim_cypher, claims)
        self.stats["claims"] = claim_count
        print(f"  Claims: {claim_count:,}")

        # Load Evidence nodes
        evidence_cypher = """
        UNWIND $batch AS row
        MERGE (e:Evidence {id: row.id})
        SET e.quote = row.quote,
            e.char_start = row.char_start,
            e.char_end = row.char_end,
            e.evidence_verified = row.evidence_verified,
            e.confidence = row.confidence,
            e.email_date = row.email_date,
            e.message_id = row.message_id,
            e.is_deleted = row.is_deleted
        """
        ev_count = _run_in_batches(session, evidence_cypher, evidences)
        self.stats["evidences"] = ev_count
        print(f"  Evidences: {ev_count:,}")

    # ----------------------------------------------------------
    # PHASE 2: EDGES
    # ----------------------------------------------------------

    def _create_claim_subject_object_edges(self, session: Session):
        """
        Create SUBJECT and OBJECT edges from Claim to Person.

        Uses the subject_id and object_id stored on each Claim node.
        MATCH (not MERGE) for Person — if the person doesn't exist,
        that row is silently skipped (no dangling edge created).
        """
        # SUBJECT edges: Claim → Person (the person this claim is about)
        subject_cypher = """
        MATCH (c:Claim)
        WHERE c.subject_id IS NOT NULL AND c.is_deleted = false
        WITH c
        MATCH (p:Person {id: c.subject_id})
        MERGE (c)-[:SUBJECT]->(p)
        RETURN count(*) AS created
        """
        result = session.run(subject_cypher)
        subject_count = result.single()["created"]
        self.stats["subject_edges"] = subject_count
        print(f"  SUBJECT edges: {subject_count:,}")

        # OBJECT edges: Claim → Person
        object_cypher = """
        MATCH (c:Claim)
        WHERE c.object_id IS NOT NULL AND c.is_deleted = false
        WITH c
        MATCH (p:Person {id: c.object_id})
        MERGE (c)-[:OBJECT]->(p)
        RETURN count(*) AS created
        """
        result = session.run(object_cypher)
        object_count = result.single()["created"]
        self.stats["object_edges"] = object_count
        print(f"  OBJECT edges: {object_count:,}")

    def _create_evidence_message_edges(self, session: Session):
        """Create SUPPORTED_BY (Claim→Evidence) and FROM_MESSAGE (Evidence→Message) edges."""
        # SUPPORTED_BY: Claim → Evidence
        sb_cypher = """
        UNWIND $batch AS row
        MATCH (c:Claim {id: row.claim_id})
        MATCH (e:Evidence {id: row.evidence_id})
        MERGE (c)-[:SUPPORTED_BY]->(e)
        """
        sb_count = _run_in_batches(session, sb_cypher, self._supported_by_edges)
        self.stats["supported_by_edges"] = sb_count
        print(f"  SUPPORTED_BY edges: {sb_count:,}")

        # FROM_MESSAGE: Evidence → Message
        # Uses the message_id stored on each Evidence node
        fm_cypher = """
        MATCH (e:Evidence)
        WHERE e.message_id IS NOT NULL
        WITH e
        MATCH (m:Message {message_id: e.message_id})
        MERGE (e)-[:FROM_MESSAGE]->(m)
        RETURN count(*) AS created
        """
        result = session.run(fm_cypher)
        fm_count = result.single()["created"]
        self.stats["from_message_edges"] = fm_count
        print(f"  FROM_MESSAGE edges: {fm_count:,}")

    def _create_message_sender_edges(self, session: Session):
        """
        Create SENT_BY edges: Message → Person.

        Resolves the Message's from_addr (email) to a canonical Person ID
        using the email→person_id index built during Person loading.
        """
        edges = []
        # Build batch from messages that have a resolvable sender
        msg_cypher = """
        MATCH (m:Message)
        WHERE m.from_addr IS NOT NULL AND m.is_deleted = false
        RETURN m.message_id AS mid, m.from_addr AS email
        """
        result = session.run(msg_cypher)
        for record in result:
            person_id = self._email_to_person_id.get(record["email"].lower())
            if person_id:
                edges.append({
                    "message_id": record["mid"],
                    "person_id": person_id,
                })

        edge_cypher = """
        UNWIND $batch AS row
        MATCH (m:Message {message_id: row.message_id})
        MATCH (p:Person {id: row.person_id})
        MERGE (m)-[:SENT_BY]->(p)
        """
        count = _run_in_batches(session, edge_cypher, edges)
        self.stats["sent_by_edges"] = count
        print(f"  SENT_BY edges: {count:,}")

    def _create_message_recipient_edges(self, session: Session):
        """
        Create SENT_TO edges: Message → Person.

        Resolves each recipient email address to a canonical Person ID.
        Messages often have multiple recipients, so one message can have
        multiple SENT_TO edges.
        """
        subset_path = self.data_dir / "extraction_subset.jsonl"
        edges = []

        with open(subset_path) as f:
            for line in f:
                email = json.loads(line)
                mid = email["message_id"]

                if mid in self._duplicate_ids:
                    continue

                # to_addrs is a list of email strings
                for recipient in email.get("to_addrs", []) or []:
                    if not recipient:
                        continue
                    person_id = self._email_to_person_id.get(recipient.lower().strip())
                    if person_id:
                        edges.append({
                            "message_id": mid,
                            "person_id": person_id,
                        })

        # Deduplicate (same message → same person via multiple addresses)
        seen = set()
        unique_edges = []
        for e in edges:
            key = (e["message_id"], e["person_id"])
            if key not in seen:
                seen.add(key)
                unique_edges.append(e)

        edge_cypher = """
        UNWIND $batch AS row
        MATCH (m:Message {message_id: row.message_id})
        MATCH (p:Person {id: row.person_id})
        MERGE (m)-[:SENT_TO]->(p)
        """
        count = _run_in_batches(session, edge_cypher, unique_edges)
        self.stats["sent_to_edges"] = count
        print(f"  SENT_TO edges: {count:,}")

    def _create_decision_made_by_edges(self, session: Session):
        """
        Create MADE_BY edges: Decision → Person.

        384 decisions have null made_by — they simply get no edge.
        """
        made_by_items = [
            e for e in self._decision_edges_raw if e["edge_type"] == "MADE_BY"
        ]

        cypher = """
        UNWIND $batch AS row
        MATCH (d:Decision {id: row.decision_id})
        MATCH (p:Person {id: row.person_id})
        MERGE (d)-[:MADE_BY]->(p)
        """
        count = _run_in_batches(session, cypher, made_by_items)
        self.stats["made_by_edges"] = count
        print(f"  MADE_BY edges: {count:,}")

    def _create_decision_affects_edges(self, session: Session):
        """
        Create AFFECTS edges: Decision → Person or Organization.

        This is the Day 4 §9.1 resolution:
        - Match in resolution_map → create AFFECTS edge
        - No match → already stored as affects_unresolved text property

        We try Person first, then Organization. If neither exists,
        the edge is silently skipped (the string is already captured
        in affects_unresolved on the Decision node).
        """
        affects_items = [
            e for e in self._decision_edges_raw if e["edge_type"] == "AFFECTS"
        ]

        # Try matching Person first, then Organization
        cypher = """
        UNWIND $batch AS row
        MATCH (d:Decision {id: row.decision_id})
        OPTIONAL MATCH (p:Person {id: row.entity_id})
        OPTIONAL MATCH (o:Organization {id: row.entity_id})
        WITH d, coalesce(p, o) AS target
        WHERE target IS NOT NULL
        MERGE (d)-[:AFFECTS]->(target)
        RETURN count(*) AS created
        """
        # Run as one batch (affects are typically not huge)
        result = session.run(cypher, batch=affects_items)
        count = result.single()["created"]
        self.stats["affects_edges"] = count
        print(f"  AFFECTS edges: {count:,}")

    def _create_deal_party_edges(self, session: Session):
        """
        Create PARTY edges: Deal → Person or Organization.

        Resolves party names via resolution_map.
        """
        edges = []
        for item in getattr(self, "_deal_parties_raw", []):
            entity_id = self._resolution_map.get(item["party_name"])
            if entity_id:
                edges.append({
                    "deal_id": item["deal_id"],
                    "entity_id": entity_id,
                })

        if not edges:
            self.stats["party_edges"] = 0
            print(f"  PARTY edges: 0")
            return

        cypher = """
        UNWIND $batch AS row
        MATCH (d:Deal {id: row.deal_id})
        OPTIONAL MATCH (p:Person {id: row.entity_id})
        OPTIONAL MATCH (o:Organization {id: row.entity_id})
        WITH d, coalesce(p, o) AS target
        WHERE target IS NOT NULL
        MERGE (d)-[:PARTY]->(target)
        """
        count = _run_in_batches(session, cypher, edges)
        self.stats["party_edges"] = count
        print(f"  PARTY edges: {count:,}")

    def _create_supersedes_edges(self, session: Session):
        """
        Create SUPERSEDES edges between claims (temporal succession).

        If Claim A has superseded_by = Claim B's id, then B SUPERSEDES A.
        """
        cypher = """
        MATCH (old:Claim)
        WHERE old.superseded_by IS NOT NULL
        WITH old
        MATCH (new:Claim {id: old.superseded_by})
        MERGE (new)-[:SUPERSEDES]->(old)
        RETURN count(*) AS created
        """
        result = session.run(cypher)
        count = result.single()["created"]
        self.stats["supersedes_edges"] = count
        print(f"  SUPERSEDES edges: {count:,}")

    def _create_conflicts_with_edges(self, session: Session):
        """
        Create CONFLICTS_WITH edges between claims.

        Bidirectional: if A conflicts with B, both A→B and B→A exist.
        MERGE prevents duplicates.
        """
        cypher = """
        MATCH (c:Claim)
        WHERE size(c.conflicts_with) > 0
        UNWIND c.conflicts_with AS conflict_id
        WITH c, conflict_id
        MATCH (other:Claim {id: conflict_id})
        MERGE (c)-[:CONFLICTS_WITH]->(other)
        RETURN count(*) AS created
        """
        result = session.run(cypher)
        count = result.single()["created"]
        self.stats["conflicts_with_edges"] = count
        print(f"  CONFLICTS_WITH edges: {count:,}")

    # ----------------------------------------------------------
    # FILE READERS
    # ----------------------------------------------------------

    def _read_canonical_entities(self) -> dict:
        """
        Read entity_resolution_fuzzy.json and return the canonical_entities dict.

        Cached after first call (both Person and Org loading need it).
        """
        if not hasattr(self, "_cached_entities"):
            path = self.data_dir / "entity_resolution_fuzzy.json"
            data = json.loads(path.read_text())
            # The file has a top-level structure; entities are under "canonical_entities"
            self._cached_entities = data.get("canonical_entities", data)
        return self._cached_entities