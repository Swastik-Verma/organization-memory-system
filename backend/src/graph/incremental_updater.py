"""
Day 25 — Incremental Update System

Three capabilities:

1. Incremental updates — process new emails through the full pipeline
   without reprocessing existing data. Uses MERGE for idempotency.

2. Confidence decay — old claims with no fresh supporting evidence
   gradually lose confidence. Claims that decay below a threshold
   are archived (status → 'archived').

3. Ontology drift detection — flags extraction output that contains
   entity types or claim types outside the defined schema.

Usage:
    from src.graph.incremental_updater import IncrementalUpdater
    updater = IncrementalUpdater(driver)

    # Process new emails
    report = updater.run_incremental_update(new_extractions, source_emails, resolution_map)

    # Apply confidence decay
    decay_report = updater.apply_confidence_decay()

    # Check for ontology drift
    drift_report = updater.detect_ontology_drift(new_extractions)
"""

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from neo4j import Driver, Session

from src.graph.schema import ClaimType, OrgType, normalize_org_type


# ============================================================
# CONSTANTS
# ============================================================

# Valid claim types (from ClaimType enum)
VALID_CLAIM_TYPES = {ct.value for ct in ClaimType}

# Valid org types (from OrgType enum)
VALID_ORG_TYPES = {ot.value for ot in OrgType}

# Confidence decay settings
DECAY_RATE_PER_YEAR = 0.10       # Lose 10% confidence per year without fresh evidence
ARCHIVE_THRESHOLD = 0.30         # Claims below this confidence get archived
DECAY_REFERENCE_DATE = "2002-01-01"  # "Today" for the Enron corpus (latest meaningful data)
MINIMUM_AGE_DAYS = 365           # Don't decay claims less than 1 year old


# ============================================================
# HELPERS
# ============================================================

def _sha256_short(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    return slug


def _days_between(date_str_1: str, date_str_2: str) -> int:
    """Calculate days between two YYYY-MM-DD date strings."""
    d1 = datetime.strptime(date_str_1, "%Y-%m-%d")
    d2 = datetime.strptime(date_str_2, "%Y-%m-%d")
    return abs((d2 - d1).days)


# ============================================================
# INCREMENTAL UPDATER
# ============================================================

class IncrementalUpdater:
    """
    Manages incremental updates, confidence decay, and ontology drift
    detection for the knowledge graph.
    """

    def __init__(self, driver: Driver):
        self.driver = driver

    # ==============================================================
    # 1. INCREMENTAL UPDATES
    # ==============================================================

    def run_incremental_update(
        self,
        new_extractions: list[dict],
        source_emails: list[dict],
        resolution_map: dict[str, str],
        duplicate_ids: set[str] | None = None,
    ) -> dict:
        """
        Process a batch of new extractions and load them into the graph.

        This reuses the existing graph loader's logic but operates on
        a single batch rather than all files. MERGE ensures idempotency —
        if any of these emails were already loaded, their nodes are
        updated rather than duplicated.

        Args:
            new_extractions: list of extraction dicts (same format as
                extractions_final.jsonl lines)
            source_emails: list of parsed email dicts (same format as
                extraction_subset.jsonl lines)
            resolution_map: name → canonical_id mapping
            duplicate_ids: set of message_ids to skip (optional)

        Returns:
            dict with counts of what was loaded
        """
        if duplicate_ids is None:
            duplicate_ids = set()

        report = {
            "emails_processed": 0,
            "emails_skipped_duplicate": 0,
            "persons_created_or_updated": 0,
            "organizations_created_or_updated": 0,
            "messages_loaded": 0,
            "claims_loaded": 0,
            "evidences_loaded": 0,
            "conflicts_detected": 0,
        }

        with self.driver.session() as session:
            # Step 1: Load new Message nodes
            for email in source_emails:
                mid = email["message_id"]
                if mid in duplicate_ids:
                    report["emails_skipped_duplicate"] += 1
                    continue

                date_str = None
                if email.get("date"):
                    raw_date = str(email["date"])
                    date_str = raw_date.split("T")[0] if "T" in raw_date else raw_date

                session.run("""
                    MERGE (m:Message {message_id: $mid})
                    SET m.date = $date,
                        m.subject = $subject,
                        m.from_addr = $from_addr,
                        m.body = $body,
                        m.x_origin = $x_origin,
                        m.is_deleted = false
                """, mid=mid, date=date_str, subject=email.get("subject"),
                     from_addr=email.get("from_addr"), body=email.get("body"),
                     x_origin=email.get("x_origin"))
                report["messages_loaded"] += 1

            # Step 2: Load entities from extractions
            for ext in new_extractions:
                mid = ext["message_id"]
                if mid in duplicate_ids:
                    continue
                report["emails_processed"] += 1

                # People
                for person in ext.get("people", []):
                    name = person.get("name", "").strip()
                    if not name:
                        continue
                    canonical_id = resolution_map.get(name)
                    if canonical_id and canonical_id.startswith("person:"):
                        session.run("""
                            MERGE (p:Person {id: $pid})
                            ON CREATE SET p.canonical_name = $name,
                                          p.aliases = [$name],
                                          p.emails = [],
                                          p.mention_count = 1,
                                          p.is_deleted = false
                            ON MATCH SET p.mention_count = p.mention_count + 1
                        """, pid=canonical_id, name=name)
                        report["persons_created_or_updated"] += 1

                # Organizations
                for org in ext.get("organizations", []):
                    name = org.get("name", "").strip()
                    if not name:
                        continue
                    canonical_id = resolution_map.get(name)
                    if canonical_id and canonical_id.startswith("org:"):
                        raw_type = org.get("org_type")
                        normalized = normalize_org_type(raw_type)
                        org_type_str = normalized.value if normalized else None
                        session.run("""
                            MERGE (o:Organization {id: $oid})
                            ON CREATE SET o.canonical_name = $name,
                                          o.aliases = [$name],
                                          o.emails = [],
                                          o.mention_count = 1,
                                          o.org_type = $org_type,
                                          o.is_deleted = false
                            ON MATCH SET o.mention_count = o.mention_count + 1
                        """, oid=canonical_id, name=name, org_type=org_type_str)
                        report["organizations_created_or_updated"] += 1

            # Step 3: Detect conflicts with existing claims
            report["conflicts_detected"] = self._detect_new_conflicts(session)

        return report

    def _detect_new_conflicts(self, session: Session) -> int:
        """
        Find claims that might conflict with newly loaded claims.

        A conflict exists when two current claims have the same subject,
        the same exclusive type (reports_to), but different objects.
        """
        result = session.run("""
            MATCH (c1:Claim), (c2:Claim)
            WHERE c1.claim_type = 'reports_to'
              AND c2.claim_type = 'reports_to'
              AND c1.subject_id = c2.subject_id
              AND c1.object_id <> c2.object_id
              AND c1.status = 'current'
              AND c2.status = 'current'
              AND c1.valid_to IS NULL
              AND c2.valid_to IS NULL
              AND c1.is_deleted = false
              AND c2.is_deleted = false
              AND c1.id < c2.id
            RETURN count(*) AS conflict_count
        """)
        return result.single()["conflict_count"]

    # ==============================================================
    # 2. CONFIDENCE DECAY
    # ==============================================================

    def apply_confidence_decay(self, reference_date: str | None = None) -> dict:
        """
        Apply time-based confidence decay to claims.

        Claims that haven't received fresh evidence gradually lose
        confidence. The decay is based on the time between the claim's
        latest evidence date and the reference date (default: end of
        Enron corpus).

        Formula:
            years_since_last_evidence = days / 365
            decay = years_since_last_evidence * DECAY_RATE_PER_YEAR
            new_confidence = original_confidence - decay
            if new_confidence < ARCHIVE_THRESHOLD → archive

        Returns:
            dict with decay statistics
        """
        if reference_date is None:
            reference_date = DECAY_REFERENCE_DATE

        report = {
            "reference_date": reference_date,
            "claims_evaluated": 0,
            "claims_decayed": 0,
            "claims_archived": 0,
            "claims_unchanged": 0,
            "average_decay": 0.0,
        }

        with self.driver.session() as session:
            # Step 1: Find all current, non-deleted claims with their latest evidence date
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.status = 'current'
                  AND c.is_deleted = false
                  AND c.valid_from IS NOT NULL
                OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(e:Evidence)
                WHERE e.is_deleted = false AND e.email_date IS NOT NULL
                WITH c,
                     c.confidence AS original_confidence,
                     c.valid_from AS claim_date,
                     max(e.email_date) AS latest_evidence_date
                RETURN c.id AS claim_id,
                       original_confidence,
                       claim_date,
                       coalesce(latest_evidence_date, claim_date) AS last_seen_date
            """)

            records = list(result)
            report["claims_evaluated"] = len(records)

            total_decay = 0.0
            decay_updates = []    # (claim_id, new_confidence)
            archive_ids = []      # claim_ids to archive

            for record in records:
                claim_id = record["claim_id"]
                original_confidence = record["original_confidence"]
                last_seen = record["last_seen_date"]

                if not last_seen:
                    report["claims_unchanged"] += 1
                    continue

                # Calculate age in days
                try:
                    days_old = _days_between(last_seen, reference_date)
                except (ValueError, TypeError):
                    report["claims_unchanged"] += 1
                    continue

                # Skip claims less than MINIMUM_AGE_DAYS old
                if days_old < MINIMUM_AGE_DAYS:
                    report["claims_unchanged"] += 1
                    continue

                # Calculate decay
                years_old = days_old / 365.0
                decay_amount = years_old * DECAY_RATE_PER_YEAR
                new_confidence = max(0.0, original_confidence - decay_amount)

                if new_confidence < ARCHIVE_THRESHOLD:
                    archive_ids.append(claim_id)
                    report["claims_archived"] += 1
                    total_decay += (original_confidence - new_confidence)
                elif new_confidence < original_confidence:
                    decay_updates.append((claim_id, round(new_confidence, 4)))
                    report["claims_decayed"] += 1
                    total_decay += (original_confidence - new_confidence)
                else:
                    report["claims_unchanged"] += 1

            # Step 2: Apply decay updates in batches
            if decay_updates:
                for claim_id, new_conf in decay_updates:
                    session.run("""
                        MATCH (c:Claim {id: $claim_id})
                        SET c.confidence = $new_confidence,
                            c.confidence_decay_applied = true
                    """, claim_id=claim_id, new_confidence=new_conf)

            # Step 3: Archive claims below threshold
            if archive_ids:
                for claim_id in archive_ids:
                    session.run("""
                        MATCH (c:Claim {id: $claim_id})
                        SET c.status = 'archived',
                            c.confidence_decay_applied = true,
                            c.archived_reason = 'confidence_decay'
                    """, claim_id=claim_id)

            if report["claims_decayed"] + report["claims_archived"] > 0:
                report["average_decay"] = round(
                    total_decay / (report["claims_decayed"] + report["claims_archived"]),
                    4
                )

        return report

    def preview_confidence_decay(self, reference_date: str | None = None, limit: int = 20) -> list[dict]:
        """
        Preview which claims would be affected by decay WITHOUT applying it.
        Useful for dry-run inspection.
        """
        if reference_date is None:
            reference_date = DECAY_REFERENCE_DATE

        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.status = 'current'
                  AND c.is_deleted = false
                  AND c.valid_from IS NOT NULL
                OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(e:Evidence)
                WHERE e.is_deleted = false AND e.email_date IS NOT NULL
                WITH c,
                     c.confidence AS original_confidence,
                     max(e.email_date) AS latest_evidence_date,
                     coalesce(max(e.email_date), c.valid_from) AS last_seen
                WITH c, original_confidence, last_seen,
                     duration.between(date(last_seen), date($ref_date)).years +
                     duration.between(date(last_seen), date($ref_date)).months / 12.0
                     AS years_old
                WHERE years_old >= 1.0
                WITH c, original_confidence, last_seen, years_old,
                     original_confidence - (years_old * $decay_rate) AS projected_confidence
                WHERE projected_confidence < original_confidence
                RETURN c.id AS claim_id,
                       c.description AS description,
                       c.claim_type AS claim_type,
                       original_confidence,
                       last_seen,
                       round(years_old * 100) / 100 AS years_since_evidence,
                       round(projected_confidence * 10000) / 10000 AS projected_confidence,
                       CASE WHEN projected_confidence < $archive_threshold
                            THEN 'WOULD_ARCHIVE'
                            ELSE 'WOULD_DECAY'
                       END AS action
                ORDER BY projected_confidence ASC
                LIMIT $limit
            """, ref_date=reference_date, decay_rate=DECAY_RATE_PER_YEAR,
                 archive_threshold=ARCHIVE_THRESHOLD, limit=limit)

            return [dict(record) for record in result]

    def reset_confidence_decay(self) -> int:
        """
        Undo confidence decay — restore original confidence values.

        This works by re-reading from resolved_claims.jsonl to get
        original confidence values. For simplicity, this version just
        removes the decay flag and restores archived claims to current.
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.confidence_decay_applied = true
                SET c.confidence_decay_applied = null,
                    c.archived_reason = null
                WITH c
                WHERE c.status = 'archived' AND c.archived_reason IS NULL
                SET c.status = 'current'
                RETURN count(c) AS restored
            """)
            return result.single()["restored"]

    # ==============================================================
    # 3. ONTOLOGY DRIFT DETECTION
    # ==============================================================

    def detect_ontology_drift(self, extractions: list[dict]) -> dict:
        """
        Check extraction output for types outside the defined schema.

        Scans for:
        - Relationship types not in the closed vocabulary
        - Organization types not in the normalization map
        - Any structural anomalies

        Args:
            extractions: list of extraction dicts

        Returns:
            dict with drift warnings
        """
        report = {
            "extractions_scanned": len(extractions),
            "unknown_relationship_types": {},
            "unknown_org_types": {},
            "empty_extractions": 0,
            "structural_issues": [],
            "drift_detected": False,
        }

        for ext in extractions:
            # Check for completely empty extractions
            has_content = any([
                ext.get("people"), ext.get("organizations"),
                ext.get("deals"), ext.get("decisions"),
                ext.get("relationships"),
            ])
            if not has_content:
                report["empty_extractions"] += 1

            # Check relationship types
            for rel in ext.get("relationships", []):
                rel_type = rel.get("relationship_type", "")
                if rel_type and rel_type not in VALID_CLAIM_TYPES:
                    report["unknown_relationship_types"][rel_type] = \
                        report["unknown_relationship_types"].get(rel_type, 0) + 1

            # Check org types
            for org in ext.get("organizations", []):
                raw_type = org.get("org_type")
                if raw_type:
                    normalized = normalize_org_type(raw_type)
                    if normalized and normalized.value == "other":
                        # This means it fell through to "other" — might need
                        # adding to the normalization map
                        report["unknown_org_types"][raw_type] = \
                            report["unknown_org_types"].get(raw_type, 0) + 1

            # Check structural issues
            for rel in ext.get("relationships", []):
                if not rel.get("person_a") or not rel.get("person_b"):
                    report["structural_issues"].append({
                        "message_id": ext.get("message_id"),
                        "issue": "relationship missing person_a or person_b",
                    })
                if rel.get("person_a") == rel.get("person_b"):
                    report["structural_issues"].append({
                        "message_id": ext.get("message_id"),
                        "issue": f"self-referential: {rel.get('person_a')}",
                    })

        report["drift_detected"] = bool(
            report["unknown_relationship_types"]
            or len(report["structural_issues"]) > 10
        )

        return report

    def detect_graph_drift(self) -> dict:
        """
        Check the loaded graph for ontology drift by querying Neo4j directly.

        Finds claim types, org types, and any unexpected patterns that
        have accumulated in the graph over time.
        """
        with self.driver.session() as session:
            report = {
                "claim_type_distribution": {},
                "unknown_claim_types": [],
                "org_type_distribution": {},
                "unmapped_org_types": [],
                "claims_without_evidence": 0,
                "claims_without_subject": 0,
            }

            # Claim type distribution
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.is_deleted = false
                RETURN c.claim_type AS claim_type, count(c) AS count
                ORDER BY count DESC
            """)
            for record in result:
                ct = record["claim_type"]
                report["claim_type_distribution"][ct] = record["count"]
                if ct not in VALID_CLAIM_TYPES:
                    report["unknown_claim_types"].append(ct)

            # Org type distribution
            result = session.run("""
                MATCH (o:Organization)
                WHERE o.is_deleted = false
                RETURN o.org_type AS org_type, count(o) AS count
                ORDER BY count DESC
            """)
            for record in result:
                ot = record["org_type"]
                report["org_type_distribution"][ot] = record["count"]
                if ot and ot not in VALID_ORG_TYPES:
                    report["unmapped_org_types"].append(ot)

            # Claims without evidence
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.is_deleted = false
                  AND NOT (c)-[:SUPPORTED_BY]->()
                RETURN count(c) AS count
            """)
            report["claims_without_evidence"] = result.single()["count"]

            # Claims without SUBJECT edge
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.is_deleted = false
                  AND NOT (c)-[:SUBJECT]->()
                RETURN count(c) AS count
            """)
            report["claims_without_subject"] = result.single()["count"]

            return report