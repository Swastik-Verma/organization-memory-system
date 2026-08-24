"""
Day 24 — Temporal Query Engine

Provides three core temporal access patterns over the knowledge graph:
  1. Current state  — what is true RIGHT NOW about an entity
  2. Historical state — what was true AT A SPECIFIC DATE
  3. Full history   — every claim ever made about an entity, chronologically

All queries:
  - Exclude soft-deleted content (is_deleted = false)
  - Return structured dicts (ready for API serialization)
  - Handle both Person and Organization entities
  - Handle null valid_from gracefully (claims from undated emails)

Usage:
    from src.graph.temporal_queries import TemporalQueryEngine
    engine = TemporalQueryEngine(driver)
    current = engine.get_current_state("person:kean-steven-j:steven-kean-at-enron-com")
    past = engine.get_state_at("person:kean-steven-j:steven-kean-at-enron-com", "2001-03-15")
    history = engine.get_full_history("person:kean-steven-j:steven-kean-at-enron-com")
"""

from neo4j import Driver


class TemporalQueryEngine:
    """
    Temporal query interface over the Neo4j knowledge graph.
    """

    def __init__(self, driver: Driver):
        self.driver = driver

    # ==============================================================
    # ENTITY LOOKUP
    # ==============================================================

    def find_entity(self, name: str) -> list[dict]:
        """
        Find entities by partial name match. Searches both Person and
        Organization nodes. Useful for discovering canonical IDs before
        running temporal queries.

        Returns a list of {id, canonical_name, entity_type, aliases, emails}.
        """
        cypher = """
        CALL {
            MATCH (p:Person)
            WHERE p.is_deleted = false
              AND (p.canonical_name CONTAINS $name
                   OR any(a IN p.aliases WHERE a CONTAINS $name))
            RETURN p.id AS id,
                   p.canonical_name AS canonical_name,
                   'person' AS entity_type,
                   p.aliases AS aliases,
                   p.emails AS emails,
                   p.mention_count AS mention_count
            UNION ALL
            MATCH (o:Organization)
            WHERE o.is_deleted = false
              AND (o.canonical_name CONTAINS $name
                   OR any(a IN o.aliases WHERE a CONTAINS $name))
            RETURN o.id AS id,
                   o.canonical_name AS canonical_name,
                   'organization' AS entity_type,
                   o.aliases AS aliases,
                   o.emails AS emails,
                   o.mention_count AS mention_count
        }
        RETURN id, canonical_name, entity_type, aliases, emails, mention_count
        ORDER BY mention_count DESC
        """
        with self.driver.session() as session:
            result = session.run(cypher, name=name)
            return [dict(record) for record in result]

    def get_entity_profile(self, entity_id: str) -> dict | None:
        """
        Get basic profile of an entity by its canonical ID.
        Works for both Person and Organization.

        Returns {id, canonical_name, entity_type, aliases, emails, mention_count, org_type}
        or None if not found.
        """
        cypher = """
        CALL {
            MATCH (p:Person {id: $entity_id})
            WHERE p.is_deleted = false
            RETURN p.id AS id,
                   p.canonical_name AS canonical_name,
                   'person' AS entity_type,
                   p.aliases AS aliases,
                   p.emails AS emails,
                   p.mention_count AS mention_count,
                   null AS org_type
            UNION ALL
            MATCH (o:Organization {id: $entity_id})
            WHERE o.is_deleted = false
            RETURN o.id AS id,
                   o.canonical_name AS canonical_name,
                   'organization' AS entity_type,
                   o.aliases AS aliases,
                   o.emails AS emails,
                   o.mention_count AS mention_count,
                   o.org_type AS org_type
        }
        RETURN id, canonical_name, entity_type, aliases, emails, mention_count, org_type
        LIMIT 1
        """
        with self.driver.session() as session:
            result = session.run(cypher, entity_id=entity_id)
            record = result.single()
            return dict(record) if record else None

    # ==============================================================
    # CORE TEMPORAL QUERIES
    # ==============================================================

    def get_current_state(self, entity_id: str, claim_type: str | None = None) -> list[dict]:
        """
        What is true RIGHT NOW about this entity?

        Returns all claims where:
          - This entity is the SUBJECT
          - valid_to IS NULL (not yet superseded)
          - status = 'current'
          - is_deleted = false

        Each result includes the claim details, the object entity name,
        and the supporting evidence count.

        Args:
            entity_id: Canonical ID of the entity
            claim_type: Optional filter (e.g. 'reports_to'). None = all types.
        """
        type_filter = "AND c.claim_type = $claim_type" if claim_type else ""

        cypher = f"""
        MATCH (c:Claim)-[:SUBJECT]->(p {{id: $entity_id}})
        WHERE c.valid_to IS NULL
          AND c.status = 'current'
          AND c.is_deleted = false
          {type_filter}
        OPTIONAL MATCH (c)-[:OBJECT]->(obj)
        WHERE obj.is_deleted = false
        OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(e:Evidence)
        WHERE e.is_deleted = false
        WITH c, obj,
             count(e) AS evidence_count
        RETURN c.id AS claim_id,
               c.claim_type AS claim_type,
               c.description AS description,
               c.confidence AS confidence,
               c.valid_from AS valid_from,
               c.mention_count AS mention_count,
               obj.canonical_name AS object_name,
               obj.id AS object_id,
               evidence_count
        ORDER BY c.confidence DESC, c.mention_count DESC
        """
        params = {"entity_id": entity_id}
        if claim_type:
            params["claim_type"] = claim_type

        with self.driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    def get_state_at(self, entity_id: str, date: str, claim_type: str | None = None) -> list[dict]:
        """
        What was true about this entity AT A SPECIFIC DATE?

        Returns all claims where:
          - This entity is the SUBJECT
          - valid_from <= date (claim existed by that date)
          - valid_to IS NULL OR valid_to > date (claim hadn't been superseded yet)
          - is_deleted = false
          - Claims with null valid_from are EXCLUDED (undated emails
            can't be placed in a timeline)

        Args:
            entity_id: Canonical ID of the entity
            date: ISO date string like '2001-03-15'
            claim_type: Optional filter. None = all types.
        """
        type_filter = "AND c.claim_type = $claim_type" if claim_type else ""

        cypher = f"""
        MATCH (c:Claim)-[:SUBJECT]->(p {{id: $entity_id}})
        WHERE c.valid_from IS NOT NULL
          AND c.valid_from <= $date
          AND (c.valid_to IS NULL OR c.valid_to > $date)
          AND c.is_deleted = false
          {type_filter}
        OPTIONAL MATCH (c)-[:OBJECT]->(obj)
        WHERE obj.is_deleted = false
        OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(e:Evidence)
        WHERE e.is_deleted = false
        WITH c, obj,
             count(e) AS evidence_count
        RETURN c.id AS claim_id,
               c.claim_type AS claim_type,
               c.description AS description,
               c.confidence AS confidence,
               c.valid_from AS valid_from,
               c.valid_to AS valid_to,
               c.status AS status,
               c.mention_count AS mention_count,
               obj.canonical_name AS object_name,
               obj.id AS object_id,
               evidence_count
        ORDER BY c.claim_type, c.valid_from
        """
        params = {"entity_id": entity_id, "date": date}
        if claim_type:
            params["claim_type"] = claim_type

        with self.driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    def get_full_history(self, entity_id: str, claim_type: str | None = None) -> list[dict]:
        """
        Every claim ever made about this entity, ordered chronologically.

        Returns ALL claims regardless of status (current, superseded, review).
        Includes validity windows and supersession info so the caller can
        reconstruct the full timeline.

        Claims with null valid_from are included at the end (sorted last).

        Args:
            entity_id: Canonical ID of the entity
            claim_type: Optional filter. None = all types.
        """
        type_filter = "AND c.claim_type = $claim_type" if claim_type else ""

        cypher = f"""
        MATCH (c:Claim)-[:SUBJECT]->(p {{id: $entity_id}})
        WHERE c.is_deleted = false
          {type_filter}
        OPTIONAL MATCH (c)-[:OBJECT]->(obj)
        WHERE obj.is_deleted = false
        OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(e:Evidence)
        WHERE e.is_deleted = false
        WITH c, obj,
             count(e) AS evidence_count
        RETURN c.id AS claim_id,
               c.claim_type AS claim_type,
               c.description AS description,
               c.confidence AS confidence,
               c.valid_from AS valid_from,
               c.valid_to AS valid_to,
               c.status AS status,
               c.mention_count AS mention_count,
               c.supersedes AS supersedes,
               c.superseded_by AS superseded_by,
               c.conflicts_with AS conflicts_with,
               obj.canonical_name AS object_name,
               obj.id AS object_id,
               evidence_count
        ORDER BY
            CASE WHEN c.valid_from IS NULL THEN 1 ELSE 0 END,
            c.valid_from,
            c.claim_type
        """
        params = {"entity_id": entity_id}
        if claim_type:
            params["claim_type"] = claim_type

        with self.driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    # ==============================================================
    # EVIDENCE RETRIEVAL
    # ==============================================================

    def get_evidence_for_claim(self, claim_id: str) -> list[dict]:
        """
        Get all evidence supporting a specific claim, with source
        email metadata.

        This is the "click a citation → see the proof" path.
        Returns evidence quote, verification status, and source email details.
        """
        cypher = """
        MATCH (c:Claim {id: $claim_id})-[:SUPPORTED_BY]->(e:Evidence)
        WHERE e.is_deleted = false
        OPTIONAL MATCH (e)-[:FROM_MESSAGE]->(m:Message)
        WHERE m.is_deleted = false
        RETURN e.id AS evidence_id,
               e.quote AS quote,
               e.char_start AS char_start,
               e.char_end AS char_end,
               e.evidence_verified AS evidence_verified,
               e.confidence AS confidence,
               e.email_date AS email_date,
               m.message_id AS message_id,
               m.subject AS email_subject,
               m.from_addr AS sender,
               m.date AS email_date_from_message
        ORDER BY e.email_date
        """
        with self.driver.session() as session:
            result = session.run(cypher, claim_id=claim_id)
            return [dict(record) for record in result]

    def get_full_email(self, message_id: str) -> dict | None:
        """
        Get the full email body for the evidence panel.

        When a user clicks an evidence quote, the frontend shows the
        full email with the quote highlighted using char_start/char_end.
        """
        cypher = """
        MATCH (m:Message {message_id: $message_id})
        WHERE m.is_deleted = false
        RETURN m.message_id AS message_id,
               m.date AS date,
               m.subject AS subject,
               m.from_addr AS from_addr,
               m.body AS body,
               m.x_origin AS x_origin
        """
        with self.driver.session() as session:
            result = session.run(cypher, message_id=message_id)
            record = result.single()
            return dict(record) if record else None

    # ==============================================================
    # RELATIONSHIP QUERIES (both directions)
    # ==============================================================

    def get_relationships_about(self, entity_id: str, claim_type: str | None = None,
                                 current_only: bool = True) -> list[dict]:
        """
        Get claims where this entity is the SUBJECT.
        "Tell me about this person's relationships."

        Args:
            current_only: If True, only current claims. If False, all.
        """
        status_filter = "AND c.status = 'current' AND c.valid_to IS NULL" if current_only else ""
        type_filter = "AND c.claim_type = $claim_type" if claim_type else ""

        cypher = f"""
        MATCH (c:Claim)-[:SUBJECT]->(p {{id: $entity_id}})
        WHERE c.is_deleted = false
          {status_filter}
          {type_filter}
        OPTIONAL MATCH (c)-[:OBJECT]->(obj)
        WHERE obj.is_deleted = false
        RETURN c.id AS claim_id,
               c.claim_type AS claim_type,
               c.description AS description,
               c.confidence AS confidence,
               c.valid_from AS valid_from,
               c.valid_to AS valid_to,
               c.status AS status,
               obj.canonical_name AS object_name,
               obj.id AS object_id
        ORDER BY c.claim_type, c.valid_from
        """
        params = {"entity_id": entity_id}
        if claim_type:
            params["claim_type"] = claim_type

        with self.driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    def get_relationships_involving(self, entity_id: str, claim_type: str | None = None,
                                     current_only: bool = True) -> list[dict]:
        """
        Get claims where this entity is EITHER the subject OR the object.
        "Tell me everything involving this person."

        This is the broader query — for example, not just who Kean reports to
        but also who reports to Kean.
        """
        status_filter = "AND c.status = 'current' AND c.valid_to IS NULL" if current_only else ""
        type_filter = "AND c.claim_type = $claim_type" if claim_type else ""

        cypher = f"""
        MATCH (c:Claim)
        WHERE c.is_deleted = false
          {status_filter}
          {type_filter}
        WITH c
        MATCH (c)-[:SUBJECT]->(subj)
        MATCH (c)-[:OBJECT]->(obj)
        WHERE subj.id = $entity_id OR obj.id = $entity_id
        RETURN c.id AS claim_id,
               c.claim_type AS claim_type,
               c.description AS description,
               c.confidence AS confidence,
               c.valid_from AS valid_from,
               c.valid_to AS valid_to,
               c.status AS status,
               subj.canonical_name AS subject_name,
               subj.id AS subject_id,
               obj.canonical_name AS object_name,
               obj.id AS object_id
        ORDER BY c.claim_type, c.valid_from
        """
        params = {"entity_id": entity_id}
        if claim_type:
            params["claim_type"] = claim_type

        with self.driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    # ==============================================================
    # DECISION & DEAL QUERIES
    # ==============================================================

    def get_decisions_by(self, entity_id: str) -> list[dict]:
        """Get all decisions made by this person."""
        cypher = """
        MATCH (d:Decision)-[:MADE_BY]->(p {id: $entity_id})
        WHERE d.is_deleted = false
        RETURN d.id AS decision_id,
               d.description AS description,
               d.made_by_name AS made_by,
               d.affects_unresolved AS affects_unresolved
        ORDER BY d.id
        """
        with self.driver.session() as session:
            result = session.run(cypher, entity_id=entity_id)
            return [dict(record) for record in result]

    def get_decisions_affecting(self, entity_id: str) -> list[dict]:
        """Get all decisions that affect this entity."""
        cypher = """
        MATCH (d:Decision)-[:AFFECTS]->(target {id: $entity_id})
        WHERE d.is_deleted = false
        RETURN d.id AS decision_id,
               d.description AS description,
               d.made_by_name AS made_by,
               d.affects_unresolved AS affects_unresolved
        ORDER BY d.id
        """
        with self.driver.session() as session:
            result = session.run(cypher, entity_id=entity_id)
            return [dict(record) for record in result]

    def get_deals_involving(self, entity_id: str) -> list[dict]:
        """Get all deals where this entity is a party."""
        cypher = """
        MATCH (d:Deal)-[:PARTY]->(target {id: $entity_id})
        WHERE d.is_deleted = false
        RETURN d.id AS deal_id,
               d.name AS deal_name,
               d.status AS status
        ORDER BY d.name
        """
        with self.driver.session() as session:
            result = session.run(cypher, entity_id=entity_id)
            return [dict(record) for record in result]

    # ==============================================================
    # CONFLICT & REVIEW QUERIES
    # ==============================================================

    def get_conflicts(self, entity_id: str | None = None) -> list[dict]:
        """
        Get unresolved conflicts. If entity_id is provided, only conflicts
        involving that entity. Otherwise all conflicts.
        """
        entity_filter = """
        AND (c1.subject_id = $entity_id OR c1.object_id = $entity_id)
        """ if entity_id else ""

        cypher = f"""
        MATCH (c1:Claim)-[:CONFLICTS_WITH]->(c2:Claim)
        WHERE c1.status = 'review'
          AND c1.is_deleted = false
          AND c2.is_deleted = false
          AND id(c1) < id(c2)
          {entity_filter}
        RETURN c1.id AS claim_a_id,
               c1.description AS claim_a_description,
               c1.valid_from AS claim_a_date,
               c1.confidence AS claim_a_confidence,
               c2.id AS claim_b_id,
               c2.description AS claim_b_description,
               c2.valid_from AS claim_b_date,
               c2.confidence AS claim_b_confidence,
               c1.subject_name AS person,
               c1.claim_type AS claim_type
        ORDER BY c1.subject_name
        """
        params = {}
        if entity_id:
            params["entity_id"] = entity_id

        with self.driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    # ==============================================================
    # GRAPH STATISTICS
    # ==============================================================

    def get_graph_stats(self) -> dict:
        """
        Summary statistics for the health dashboard.
        """
        cypher = """
        CALL {
            MATCH (p:Person) WHERE p.is_deleted = false
            RETURN 'persons' AS metric, count(p) AS value
            UNION ALL
            MATCH (o:Organization) WHERE o.is_deleted = false
            RETURN 'organizations' AS metric, count(o) AS value
            UNION ALL
            MATCH (m:Message) WHERE m.is_deleted = false
            RETURN 'messages' AS metric, count(m) AS value
            UNION ALL
            MATCH (c:Claim) WHERE c.is_deleted = false
            RETURN 'total_claims' AS metric, count(c) AS value
            UNION ALL
            MATCH (c:Claim) WHERE c.status = 'current' AND c.is_deleted = false
            RETURN 'current_claims' AS metric, count(c) AS value
            UNION ALL
            MATCH (c:Claim) WHERE c.status = 'superseded' AND c.is_deleted = false
            RETURN 'superseded_claims' AS metric, count(c) AS value
            UNION ALL
            MATCH (c:Claim) WHERE c.status = 'review' AND c.is_deleted = false
            RETURN 'review_claims' AS metric, count(c) AS value
            UNION ALL
            MATCH (e:Evidence) WHERE e.is_deleted = false
            RETURN 'evidences' AS metric, count(e) AS value
            UNION ALL
            MATCH (d:Deal) WHERE d.is_deleted = false
            RETURN 'deals' AS metric, count(d) AS value
            UNION ALL
            MATCH (d:Decision) WHERE d.is_deleted = false
            RETURN 'decisions' AS metric, count(d) AS value
        }
        RETURN metric, value
        """
        with self.driver.session() as session:
            result = session.run(cypher)
            return {record["metric"]: record["value"] for record in result}