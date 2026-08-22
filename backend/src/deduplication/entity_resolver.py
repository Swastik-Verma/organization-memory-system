"""
Entity resolution — exact matching phase.

Collapses multiple name strings that refer to the same real-world entity
into a single canonical entity with an alias list.

Two resolution strategies (in priority order):
  1. Email match (people only)  — definitive, confidence 1.0
  2. Normalized name match      — strong, confidence 0.95

This is the EXACT matching phase (Day 16). Fuzzy matching and
LLM-assisted disambiguation happen in Day 17.

Downstream usage:
  During Neo4j ingestion, look up any name string in the resolution map
  to get the canonical_id. All aliases point to the same graph node.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

# Titles/honorifics to strip from person names
PERSON_TITLES = frozenset({
    "mr", "mrs", "ms", "dr", "prof", "professor",
    "jr", "sr", "ii", "iii", "iv", "esq",
    "rev", "hon", "sgt", "cpl", "pvt", "capt",
})

# Corporate suffixes to strip from organization names
ORG_SUFFIXES = frozenset({
    "inc", "corp", "corporation", "llc", "ltd", "limited",
    "co", "lp", "lc", "plc",
})


def normalize_person_name(name: str) -> str:
    """Normalize a person name for exact matching.

    Steps:
      1. Lowercase
      2. Remove commas and periods
      3. Split into parts
      4. Remove titles/honorifics
      5. Remove empty parts
      6. Sort parts alphabetically  ← handles "Last, First" vs "First Last"

    Examples:
      "Steven Kean"      → "kean steven"
      "Kean, Steven"     → "kean steven"      (comma removed, sorted)
      "Mr. Steven Kean"  → "kean steven"      (title stripped)
      "steven.kean"      → "kean steven"      (period → space, sorted)
      "STEVEN KEAN"      → "kean steven"      (lowercased)

    Does NOT catch:
      "Ken" vs "Kenneth"         → different normalized forms (Day 17)
      "Steven J Kean" vs "Steven Kean" → different (Day 17)
    """
    if not name:
        return ""

    name = name.lower().strip()
    # Replace commas and periods with spaces
    name = name.replace(",", " ").replace(".", " ")
    # Split into parts
    parts = name.split()
    # Remove titles
    parts = [p for p in parts if p not in PERSON_TITLES]
    # Remove empty/whitespace parts
    parts = [p for p in parts if p.strip()]
    # Sort alphabetically (handles First Last vs Last First)
    parts.sort()

    return " ".join(parts)


def normalize_org_name(name: str) -> str:
    """Normalize an organization name for exact matching.

    Steps:
      1. Lowercase
      2. Remove periods and commas
      3. Split into parts
      4. Remove corporate suffixes
      5. Remove empty parts
      6. Rejoin (do NOT sort — org name word order matters)

    Examples:
      "Enron Corp."        → "enron"
      "Enron Corporation"  → "enron"
      "enron, inc."        → "enron"
      "Enron North America" → "enron north america"  (NOT sorted)

    Does NOT catch:
      "Enron" vs "ENE"              → abbreviation (Day 17)
      "Pacific Gas & Electric" vs "PG&E" → abbreviation (Day 17)
    """
    if not name:
        return ""

    name = name.lower().strip()
    name = name.replace(".", "").replace(",", "")
    parts = name.split()
    # Only strip if the suffix is at the END, not in the middle
    # "International Paper" should keep "International"
    # "Enron International" should also keep "International"
    # But "Enron Inc" should strip "Inc"
    # Simple rule: strip trailing parts that are suffixes
    while parts and parts[-1] in ORG_SUFFIXES:
        parts.pop()
    parts = [p for p in parts if p.strip()]

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CanonicalEntity:
    """A resolved entity representing one real-world person or organization."""
    canonical_id: str
    canonical_name: str
    entity_type: str              # "person" or "organization"
    aliases: set[str] = field(default_factory=set)
    emails: set[str] = field(default_factory=set)
    mention_count: int = 0
    org_type: str | None = None   # only for organizations

    def to_dict(self) -> dict:
        return {
            "canonical_id": self.canonical_id,
            "canonical_name": self.canonical_name,
            "entity_type": self.entity_type,
            "aliases": sorted(self.aliases),
            "emails": sorted(self.emails),
            "mention_count": self.mention_count,
            "org_type": self.org_type,
        }


@dataclass
class MergeRecord:
    """Audit trail for one merge operation."""
    merged_name: str
    merged_email: str | None
    into_canonical_id: str
    into_canonical_name: str
    reason: str                   # "email_match" or "normalized_name_match"
    confidence: float
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "merged_name": self.merged_name,
            "merged_email": self.merged_email,
            "into_canonical_id": self.into_canonical_id,
            "into_canonical_name": self.into_canonical_name,
            "reason": self.reason,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Entity Resolver
# ---------------------------------------------------------------------------

def _make_person_id(normalized_name: str, email: str | None = None) -> str:
    slug = normalized_name.replace(" ", "-")
    if email:
        email_slug = email.replace("@", "-at-").replace(".", "-")
        return f"person:{slug}:{email_slug}"
    return f"person:{slug}"


def _make_org_id(normalized_name: str) -> str:
    """Generate a deterministic ID for an organization from its normalized name."""
    slug = normalized_name.replace(" ", "-")
    return f"org:{slug}"


def _choose_canonical_name(aliases: set[str], counts: dict[str, int]) -> str:
    """Pick the best display name from a set of aliases.

    Priority:
      1. Most frequent variant (most likely to be standard form)
      2. Longest (more information: "Steven Kean" > "S. Kean")
      3. Alphabetically first (deterministic tiebreaker)
    """
    return max(
        aliases,
        key=lambda name: (counts.get(name, 0), len(name), [-ord(c) for c in name]),
    )


class EntityResolver:
    """Resolves entity mentions to canonical entities via exact matching.

    Usage:
        resolver = EntityResolver()

        # Process all person mentions
        for name, email, count in person_mentions:
            resolver.resolve_person(name, email, count)

        # Process all org mentions
        for name, org_type, count in org_mentions:
            resolver.resolve_organization(name, org_type, count)

        # Get results
        resolution_map = resolver.get_resolution_map()
        stats = resolver.get_stats()
    """

    # Email addresses with more than this many distinct normalized names
    # are treated as shared/generic and skipped for email-based resolution
    SHARED_EMAIL_THRESHOLD = 5

    def __init__(self):
        # Canonical entity storage
        self._people: dict[str, CanonicalEntity] = {}       # canonical_id → entity
        self._orgs: dict[str, CanonicalEntity] = {}         # canonical_id → entity

        # Lookup indexes for people
        self._person_name_index: dict[str, list[str]] = defaultdict(list) # normalized_name → canonical_id
        self._person_email_index: dict[str, str] = {}       # email → canonical_id

        # Lookup index for organizations
        self._org_name_index: dict[str, str] = {}           # normalized_name → canonical_id

        # Track email → set of normalized names (to detect shared emails)
        self._email_names: dict[str, set[str]] = defaultdict(set)

        # Merge audit log
        self._merge_log: list[MergeRecord] = []

        # Track raw name → count for canonical name selection
        self._person_name_counts: dict[str, int] = defaultdict(int)
        self._org_name_counts: dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------
    # Person resolution
    # ------------------------------------------------------------------

    def resolve_person(
        self, name: str, email: str | None = None, count: int = 1
    ) -> str:
        """Resolve a person mention to a canonical entity.

        Args:
            name:  the name string as it appears in the extraction
            email: the email address (may be None)
            count: how many times this (name, email) pair appears

        Returns:
            canonical_id of the resolved entity
        """
        if not name or not name.strip():
            return ""

        name = name.strip()
        normalized = normalize_person_name(name)
        if not normalized:
            return ""

        self._person_name_counts[name] += count

        # Clean up email
        if email:
            email = email.strip().lower()
            if not email or "@" not in email:
                email = None

        # Track which names appear with which emails (for shared email detection)
        if email:
            self._email_names[email].add(normalized)

        # --- Resolution logic (priority order) ---

        # 1. Email match (definitive)
        if email and not self._is_shared_email(email):
            if email in self._person_email_index:
                canonical_id = self._person_email_index[email]
                entity = self._people[canonical_id]
                self._merge_person_into(entity, name, email, count, "email_match", 1.0)
                return canonical_id

        # 2. Normalized name match
        if normalized in self._person_name_index:
            candidates = self._person_name_index[normalized]

            # Find the best match among candidates
            matched_id = None
            for cid in candidates:
                entity = self._people[cid]

                # Guard: if BOTH sides have emails and they DON'T overlap,
                # these are different people who share a name — skip this candidate.
                if email and entity.emails and email not in entity.emails:
                    continue

                # If new mention has email that overlaps, this is a strong match
                if email and email in entity.emails:
                    matched_id = cid
                    break  # definitive match, stop looking

                # No conflict — this is a viable match. Pick highest mention count.
                if matched_id is None or entity.mention_count > self._people[matched_id].mention_count:
                    matched_id = cid

            if matched_id is not None:
                self._merge_person_into(self._people[matched_id], name, email, count, "normalized_name_match", 0.95)
                return matched_id

        # 3. No match — create new canonical entity
        canonical_id = _make_person_id(normalized, email)

        # Handle ID collision (different normalized names producing same slug — unlikely but safe)
        if canonical_id in self._people:
            canonical_id = f"{canonical_id}_{len(self._people)}"

        entity = CanonicalEntity(
            canonical_id=canonical_id,
            canonical_name=name,     # will be updated later to best variant
            entity_type="person",
            aliases={name},
            emails={email} if email else set(),
            mention_count=count,
        )
        self._people[canonical_id] = entity
        self._person_name_index[normalized].append(canonical_id)
        if email and not self._is_shared_email(email):
            self._person_email_index[email] = canonical_id

        return canonical_id

    def _merge_person_into(
        self,
        entity: CanonicalEntity,
        name: str,
        email: str | None,
        count: int,
        reason: str,
        confidence: float,
    ) -> None:
        """Merge a new mention into an existing canonical entity."""
        is_new_alias = name not in entity.aliases

        entity.aliases.add(name)
        entity.mention_count += count
        if email:
            entity.emails.add(email)
            if not self._is_shared_email(email):
                self._person_email_index[email] = entity.canonical_id

        # Also register this name's normalized form in the name index
        normalized = normalize_person_name(name)
        if normalized and entity.canonical_id not in self._person_name_index.get(normalized, []):
            self._person_name_index[normalized].append(entity.canonical_id)

        # Log the merge (only for genuinely new aliases, not repeat occurrences)
        if is_new_alias:
            self._merge_log.append(MergeRecord(
                merged_name=name,
                merged_email=email,
                into_canonical_id=entity.canonical_id,
                into_canonical_name=entity.canonical_name,
                reason=reason,
                confidence=confidence,
            ))

    def _is_shared_email(self, email: str) -> bool:
        """Check if an email address is shared/generic (too many distinct names)."""
        return len(self._email_names.get(email, set())) > self.SHARED_EMAIL_THRESHOLD

    # ------------------------------------------------------------------
    # Organization resolution
    # ------------------------------------------------------------------

    def resolve_organization(
        self, name: str, org_type: str | None = None, count: int = 1
    ) -> str:
        """Resolve an organization mention to a canonical entity.

        Organizations don't have email addresses, so resolution is
        by normalized name only.
        """
        if not name or not name.strip():
            return ""

        name = name.strip()
        normalized = normalize_org_name(name)
        if not normalized:
            return ""

        self._org_name_counts[name] += count

        # Check name index
        if normalized in self._org_name_index:
            canonical_id = self._org_name_index[normalized]
            entity = self._orgs[canonical_id]
            is_new = name not in entity.aliases
            entity.aliases.add(name)
            entity.mention_count += count
            # Keep the most specific org_type
            if org_type and not entity.org_type:
                entity.org_type = org_type

            if is_new:
                self._merge_log.append(MergeRecord(
                    merged_name=name,
                    merged_email=None,
                    into_canonical_id=entity.canonical_id,
                    into_canonical_name=entity.canonical_name,
                    reason="normalized_name_match",
                    confidence=0.95,
                ))
            return canonical_id

        # No match — create new
        canonical_id = _make_org_id(normalized)
        if canonical_id in self._orgs:
            canonical_id = f"{canonical_id}_{len(self._orgs)}"

        entity = CanonicalEntity(
            canonical_id=canonical_id,
            canonical_name=name,
            entity_type="organization",
            aliases={name},
            mention_count=count,
            org_type=org_type,
        )
        self._orgs[canonical_id] = entity
        self._org_name_index[normalized] = canonical_id

        return canonical_id

    # ------------------------------------------------------------------
    # Finalization and output
    # ------------------------------------------------------------------

    def finalize(self) -> None:
        """Update canonical names to the best variant based on frequency.

        Call this after all mentions have been processed.
        """
        for entity in self._people.values():
            entity.canonical_name = _choose_canonical_name(
                entity.aliases, self._person_name_counts
            )
        for entity in self._orgs.values():
            entity.canonical_name = _choose_canonical_name(
                entity.aliases, self._org_name_counts
            )

    def get_resolution_map(self) -> dict[str, str]:
        """Return a mapping: original_name → canonical_id.

        Used during Neo4j ingestion to look up any name string and get
        the canonical entity it belongs to.
        """
        result = {}
        for entity in self._people.values():
            for alias in entity.aliases:
                result[alias] = entity.canonical_id
        for entity in self._orgs.values():
            for alias in entity.aliases:
                result[alias] = entity.canonical_id
        return result

    def get_canonical_entities(self) -> dict[str, dict]:
        """Return all canonical entities keyed by canonical_id."""
        result = {}
        for cid, entity in self._people.items():
            result[cid] = entity.to_dict()
        for cid, entity in self._orgs.items():
            result[cid] = entity.to_dict()
        return result

    def get_merge_log(self) -> list[dict]:
        """Return the full merge audit log."""
        return [m.to_dict() for m in self._merge_log]

    def get_stats(self) -> dict:
        """Return resolution statistics."""
        email_merges = sum(
            1 for m in self._merge_log if m.reason == "email_match"
        )
        name_merges = sum(
            1 for m in self._merge_log if m.reason == "normalized_name_match"
        )

        # Count shared emails that were skipped
        shared_emails = [
            email for email, names in self._email_names.items()
            if len(names) > self.SHARED_EMAIL_THRESHOLD
        ]

        return {
            "total_unique_person_names_input": len(self._person_name_counts),
            "canonical_people": len(self._people),
            "person_names_collapsed": len(self._person_name_counts) - len(self._people),
            "total_unique_org_names_input": len(self._org_name_counts),
            "canonical_orgs": len(self._orgs),
            "org_names_collapsed": len(self._org_name_counts) - len(self._orgs),
            "merges_by_email": email_merges,
            "merges_by_normalized_name": name_merges,
            "total_merges": email_merges + name_merges,
            "shared_emails_skipped": len(shared_emails),
            "shared_email_addresses": shared_emails,
        }