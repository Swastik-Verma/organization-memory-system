"""
Day 26 — Permission Layer

Provides role-based access control over the knowledge graph:

1. Access levels on content (claims, evidence, decisions)
2. User clearance levels
3. Query filters injected into every Cypher query
4. Access level assignment based on content heuristics

Access levels (numeric for easy comparison):
  1 = PUBLIC        — anyone
  2 = INTERNAL      — employees
  3 = CONFIDENTIAL  — management
  4 = RESTRICTED    — executives and legal only

Rule: user sees content where content.access_level <= user.clearance_level

Design principle: filtering happens in Cypher (at the database), not
in Python after results return. Restricted content never leaves Neo4j
for unauthorized users.

Usage:
    from src.graph.permissions import PermissionManager, UserContext

    user = UserContext(user_id="analyst_1", clearance_level=2)
    pm = PermissionManager(driver)

    # Assign access levels to graph content
    pm.assign_access_levels()

    # Query with permission filtering
    from src.graph.temporal_queries import TemporalQueryEngine
    engine = TemporalQueryEngine(driver)
    results = pm.filtered_current_state(engine, entity_id, user)
"""

from dataclasses import dataclass, field
from neo4j import Driver, Session


# ============================================================
# ACCESS LEVELS
# ============================================================

PUBLIC = 1
INTERNAL = 2
CONFIDENTIAL = 3
RESTRICTED = 4

ACCESS_LEVEL_NAMES = {
    1: "PUBLIC",
    2: "INTERNAL",
    3: "CONFIDENTIAL",
    4: "RESTRICTED",
}


# ============================================================
# USER CONTEXT
# ============================================================

@dataclass
class UserContext:
    """
    Represents an authenticated user making a query.

    In production, this would come from JWT token claims.
    For the portfolio project, it's constructed manually.
    """
    user_id: str
    clearance_level: int = PUBLIC  # default: lowest access
    roles: list[str] = field(default_factory=list)

    def can_access(self, access_level: int) -> bool:
        """Check if this user can see content at the given access level."""
        return self.clearance_level >= access_level


# ============================================================
# KEYWORDS FOR ACCESS LEVEL ASSIGNMENT
# ============================================================

# Keywords that suggest higher access levels (case-insensitive matching)
CONFIDENTIAL_KEYWORDS = [
    "confidential", "do not distribute", "do not forward",
    "not for distribution", "privileged", "attorney-client",
    "attorney client", "board of directors", "board meeting",
    "executive committee", "compensation", "salary",
    "termination", "fired", "severance",
]

RESTRICTED_KEYWORDS = [
    "restricted", "top secret", "legal hold",
    "litigation", "subpoena", "sec investigation",
    "sec inquiry", "grand jury", "indictment",
    "criminal", "fraud", "whistleblower",
]

# Executive mailboxes — emails from these get CONFIDENTIAL by default
EXECUTIVE_ORIGINS = {
    "LAY-K", "KITCHEN-L",
}

# Legal mailboxes — emails from these get INTERNAL by default
LEGAL_ORIGINS = {
    "MANN-K", "NEMEC-G", "JONES-T",
}


# ============================================================
# PERMISSION MANAGER
# ============================================================

class PermissionManager:
    """
    Manages access levels on graph content and provides
    permission-filtered query wrappers.
    """

    def __init__(self, driver: Driver):
        self.driver = driver

    # ==============================================================
    # ACCESS LEVEL ASSIGNMENT
    # ==============================================================

    def assign_access_levels(self) -> dict:
        """
        Assign access levels to all content in the graph based on
        heuristics:

        1. Messages: level based on x_origin (mailbox) and content keywords
        2. Evidence: inherits from its source message
        3. Claims: inherits the HIGHEST level from its evidence
        4. Decisions: level based on content and made_by person

        Returns a report of what was assigned.
        """
        report = {
            "messages_classified": 0,
            "evidence_classified": 0,
            "claims_classified": 0,
            "decisions_classified": 0,
            "level_distribution": {1: 0, 2: 0, 3: 0, 4: 0},
        }

        with self.driver.session() as session:
            # Step 1: Classify messages
            report["messages_classified"] = self._classify_messages(session)

            # Step 2: Evidence inherits from source message
            report["evidence_classified"] = self._classify_evidence(session)

            # Step 3: Claims inherit highest level from evidence
            report["claims_classified"] = self._classify_claims(session)

            # Step 4: Decisions based on content
            report["decisions_classified"] = self._classify_decisions(session)

            # Step 5: Count distribution
            result = session.run("""
                MATCH (c:Claim)
                WHERE c.is_deleted = false AND c.access_level IS NOT NULL
                RETURN c.access_level AS level, count(c) AS cnt
            """)
            for record in result:
                level = record["level"]
                if level in report["level_distribution"]:
                    report["level_distribution"][level] = record["cnt"]

        return report

    def _classify_messages(self, session: Session) -> int:
        """
        Assign access levels to Message nodes based on:
        - x_origin mailbox (executive/legal mailboxes get higher levels)
        - Content keywords in subject and body
        """
        # Default: all messages start at PUBLIC
        session.run("""
            MATCH (m:Message)
            WHERE m.access_level IS NULL
            SET m.access_level = 1
        """)

        # Legal mailboxes → INTERNAL
        if LEGAL_ORIGINS:
            session.run("""
                MATCH (m:Message)
                WHERE m.x_origin IN $origins
                SET m.access_level = 2
            """, origins=list(LEGAL_ORIGINS))

        # Executive mailboxes → CONFIDENTIAL
        if EXECUTIVE_ORIGINS:
            session.run("""
                MATCH (m:Message)
                WHERE m.x_origin IN $origins
                SET m.access_level = 3
            """, origins=list(EXECUTIVE_ORIGINS))

        # Keyword-based escalation (subject line)
        for keyword in CONFIDENTIAL_KEYWORDS:
            session.run("""
                MATCH (m:Message)
                WHERE (toLower(m.subject) CONTAINS $kw
                       OR toLower(m.body) CONTAINS $kw)
                  AND m.access_level < 3
                SET m.access_level = 3
            """, kw=keyword.lower())

        for keyword in RESTRICTED_KEYWORDS:
            session.run("""
                MATCH (m:Message)
                WHERE (toLower(m.subject) CONTAINS $kw
                       OR toLower(m.body) CONTAINS $kw)
                  AND m.access_level < 4
                SET m.access_level = 4
            """, kw=keyword.lower())

        result = session.run("""
            MATCH (m:Message)
            WHERE m.access_level IS NOT NULL
            RETURN count(m) AS total
        """)
        return result.single()["total"]

    def _classify_evidence(self, session: Session) -> int:
        """Evidence inherits access level from its source message."""
        # Default: PUBLIC for evidence without a linked message
        session.run("""
            MATCH (e:Evidence)
            WHERE e.access_level IS NULL
            SET e.access_level = 1
        """)

        # Inherit from source message
        result = session.run("""
            MATCH (e:Evidence)-[:FROM_MESSAGE]->(m:Message)
            WHERE m.access_level IS NOT NULL
            SET e.access_level = m.access_level
            RETURN count(e) AS updated
        """)
        return result.single()["updated"]

    def _classify_claims(self, session: Session) -> int:
        """
        Claims inherit the HIGHEST access level from their evidence.

        If a claim is supported by 3 pieces of evidence at levels
        1, 1, 3 — the claim gets level 3. The most sensitive source
        determines the claim's classification.
        """
        # Default: PUBLIC for claims without evidence
        session.run("""
            MATCH (c:Claim)
            WHERE c.access_level IS NULL
            SET c.access_level = 1
        """)

        # Inherit max from evidence
        result = session.run("""
            MATCH (c:Claim)-[:SUPPORTED_BY]->(e:Evidence)
            WHERE e.access_level IS NOT NULL
            WITH c, max(e.access_level) AS max_level
            SET c.access_level = max_level
            RETURN count(c) AS updated
        """)
        return result.single()["updated"]

    def _classify_decisions(self, session: Session) -> int:
        """Decisions classified by content keywords and maker."""
        # Default: PUBLIC
        session.run("""
            MATCH (d:Decision)
            WHERE d.access_level IS NULL
            SET d.access_level = 1
        """)

        # Keyword escalation on description
        for keyword in CONFIDENTIAL_KEYWORDS:
            session.run("""
                MATCH (d:Decision)
                WHERE toLower(d.description) CONTAINS $kw
                  AND d.access_level < 3
                SET d.access_level = 3
            """, kw=keyword.lower())

        for keyword in RESTRICTED_KEYWORDS:
            session.run("""
                MATCH (d:Decision)
                WHERE toLower(d.description) CONTAINS $kw
                  AND d.access_level < 4
                SET d.access_level = 4
            """, kw=keyword.lower())
        
        # Inherit from source message (if message has higher level)
        session.run("""
            MATCH (d:Decision)
            WHERE d.source_message_id IS NOT NULL
            WITH d
            MATCH (m:Message {message_id: d.source_message_id})
            WHERE m.access_level > d.access_level
            SET d.access_level = m.access_level
        """)

        result = session.run("""
            MATCH (d:Decision)
            WHERE d.access_level IS NOT NULL
            RETURN count(d) AS total
        """)
        return result.single()["total"]

    # ==============================================================
    # PERMISSION-FILTERED QUERIES
    # ==============================================================

    def filtered_current_state(self, engine, entity_id: str,
                                user: UserContext,
                                claim_type: str | None = None) -> list[dict]:
        """
        Current state filtered by user's clearance level.

        Wraps the temporal query engine's get_current_state with
        an additional access_level filter.
        """
        type_filter = "AND c.claim_type = $claim_type" if claim_type else ""

        cypher = f"""
        MATCH (c:Claim)-[:SUBJECT]->(p {{id: $entity_id}})
        WHERE c.valid_to IS NULL
          AND c.status = 'current'
          AND c.is_deleted = false
          AND c.access_level <= $clearance
          {type_filter}
        OPTIONAL MATCH (c)-[:OBJECT]->(obj)
        WHERE obj.is_deleted = false
        OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(e:Evidence)
        WHERE e.is_deleted = false AND e.access_level <= $clearance
        WITH c, obj, count(e) AS evidence_count
        RETURN c.id AS claim_id,
               c.claim_type AS claim_type,
               c.description AS description,
               c.confidence AS confidence,
               c.valid_from AS valid_from,
               c.access_level AS access_level,
               obj.canonical_name AS object_name,
               obj.id AS object_id,
               evidence_count
        ORDER BY c.confidence DESC
        """
        params = {"entity_id": entity_id, "clearance": user.clearance_level}
        if claim_type:
            params["claim_type"] = claim_type

        with self.driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    def filtered_state_at(self, entity_id: str, date: str,
                           user: UserContext,
                           claim_type: str | None = None) -> list[dict]:
        """Historical state filtered by user's clearance level."""
        type_filter = "AND c.claim_type = $claim_type" if claim_type else ""

        cypher = f"""
        MATCH (c:Claim)-[:SUBJECT]->(p {{id: $entity_id}})
        WHERE c.valid_from IS NOT NULL
          AND c.valid_from <= $date
          AND (c.valid_to IS NULL OR c.valid_to > $date)
          AND c.is_deleted = false
          AND c.access_level <= $clearance
          {type_filter}
        OPTIONAL MATCH (c)-[:OBJECT]->(obj)
        WHERE obj.is_deleted = false
        OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(e:Evidence)
        WHERE e.is_deleted = false AND e.access_level <= $clearance
        WITH c, obj, count(e) AS evidence_count
        RETURN c.id AS claim_id,
               c.claim_type AS claim_type,
               c.description AS description,
               c.confidence AS confidence,
               c.valid_from AS valid_from,
               c.valid_to AS valid_to,
               c.access_level AS access_level,
               obj.canonical_name AS object_name,
               evidence_count
        ORDER BY c.claim_type, c.valid_from
        """
        params = {"entity_id": entity_id, "date": date, "clearance": user.clearance_level}
        if claim_type:
            params["claim_type"] = claim_type

        with self.driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    def filtered_full_history(self, entity_id: str,
                               user: UserContext,
                               claim_type: str | None = None) -> list[dict]:
        """Full history filtered by user's clearance level."""
        type_filter = "AND c.claim_type = $claim_type" if claim_type else ""

        cypher = f"""
        MATCH (c:Claim)-[:SUBJECT]->(p {{id: $entity_id}})
        WHERE c.is_deleted = false
          AND c.access_level <= $clearance
          {type_filter}
        OPTIONAL MATCH (c)-[:OBJECT]->(obj)
        WHERE obj.is_deleted = false
        OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(e:Evidence)
        WHERE e.is_deleted = false AND e.access_level <= $clearance
        WITH c, obj, count(e) AS evidence_count
        RETURN c.id AS claim_id,
               c.claim_type AS claim_type,
               c.description AS description,
               c.confidence AS confidence,
               c.valid_from AS valid_from,
               c.valid_to AS valid_to,
               c.status AS status,
               c.access_level AS access_level,
               obj.canonical_name AS object_name,
               evidence_count
        ORDER BY
            CASE WHEN c.valid_from IS NULL THEN 1 ELSE 0 END,
            c.valid_from
        """
        params = {"entity_id": entity_id, "clearance": user.clearance_level}
        if claim_type:
            params["claim_type"] = claim_type

        with self.driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    def filtered_evidence(self, claim_id: str, user: UserContext) -> list[dict]:
        """Evidence for a claim, filtered by user's clearance."""
        cypher = """
        MATCH (c:Claim {id: $claim_id})-[:SUPPORTED_BY]->(e:Evidence)
        WHERE e.is_deleted = false
          AND e.access_level <= $clearance
        OPTIONAL MATCH (e)-[:FROM_MESSAGE]->(m:Message)
        WHERE m.is_deleted = false
          AND m.access_level <= $clearance
        RETURN e.id AS evidence_id,
               e.quote AS quote,
               e.char_start AS char_start,
               e.char_end AS char_end,
               e.evidence_verified AS evidence_verified,
               e.access_level AS evidence_access_level,
               m.message_id AS message_id,
               m.subject AS email_subject,
               m.from_addr AS sender,
               m.date AS email_date,
               m.access_level AS message_access_level
        ORDER BY e.email_date
        """
        with self.driver.session() as session:
            result = session.run(cypher, claim_id=claim_id, clearance=user.clearance_level)
            return [dict(record) for record in result]

    # ==============================================================
    # ACCESS LEVEL QUERIES
    # ==============================================================

    def get_access_level_stats(self) -> dict:
        """Get distribution of access levels across content types."""
        with self.driver.session() as session:
            stats = {}

            for label in ["Claim", "Evidence", "Message", "Decision"]:
                result = session.run(f"""
                    MATCH (n:{label})
                    WHERE n.is_deleted = false
                    RETURN n.access_level AS level, count(n) AS cnt
                    ORDER BY level
                """)
                dist = {}
                for record in result:
                    level = record["level"]
                    level_name = ACCESS_LEVEL_NAMES.get(level, f"UNKNOWN({level})")
                    dist[level_name] = record["cnt"]
                stats[label] = dist

            return stats

    def clear_access_levels(self) -> dict:
        """Remove all access level assignments. Useful for re-classification."""
        with self.driver.session() as session:
            counts = {}
            for label in ["Claim", "Evidence", "Message", "Decision"]:
                result = session.run(f"""
                    MATCH (n:{label})
                    WHERE n.access_level IS NOT NULL
                    REMOVE n.access_level
                    RETURN count(n) AS cleared
                """)
                counts[label] = result.single()["cleared"]
            return counts