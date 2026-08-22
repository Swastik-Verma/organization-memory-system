"""
Fuzzy entity matching — Day 17.

Builds on Day 16's exact matching output. Finds merge candidates using:
  1. Middle initial stripping ("Steven J Kean" → "Steven Kean")
  2. Nickname expansion ("Ken" → "Kenneth")
  3. Same email domain + high name similarity
  4. General fuzzy matching via rapidfuzz

Auto-merges high-confidence candidates (≥ 0.85).
Optionally sends ambiguous candidates (0.70–0.85) to LLM for confirmation.
Every merge is recorded with snapshots for undo.
"""

import copy
import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Nickname lookup table
# ---------------------------------------------------------------------------

# Maps nickname → formal name. Bidirectional lookup built at runtime.
_NICKNAME_TO_FORMAL: dict[str, str] = {
    "ken": "kenneth",
    "kenny": "kenneth",
    "mike": "michael",
    "steve": "steven",
    "bob": "robert",
    "bobby": "robert",
    "rob": "robert",
    "bill": "william",
    "billy": "william",
    "will": "william",
    "jim": "james",
    "jimmy": "james",
    "jeff": "jeffrey",
    "joe": "joseph",
    "joey": "joseph",
    "tom": "thomas",
    "tommy": "thomas",
    "dick": "richard",
    "rick": "richard",
    "rich": "richard",
    "dan": "daniel",
    "danny": "daniel",
    "dave": "david",
    "liz": "elizabeth",
    "beth": "elizabeth",
    "betty": "elizabeth",
    "sue": "susan",
    "vince": "vincent",
    "vinnie": "vincent",
    "ed": "edward",
    "eddie": "edward",
    "ted": "theodore",
    "teddy": "theodore",
    "chris": "christopher",
    "matt": "matthew",
    "pat": "patrick",
    "tony": "anthony",
    "larry": "lawrence",
    "greg": "gregory",
    "doug": "douglas",
    "ron": "ronald",
    "al": "albert",
    "alex": "alexander",
    "andy": "andrew",
    "drew": "andrew",
    "charlie": "charles",
    "chuck": "charles",
    "frank": "francis",
    "fred": "frederick",
    "gerry": "gerald",
    "jerry": "gerald",
    "harry": "harold",
    "hank": "henry",
    "jack": "john",
    "jake": "jacob",
    "jenny": "jennifer",
    "kate": "katherine",
    "kathy": "katherine",
    "katie": "katherine",
    "maggie": "margaret",
    "meg": "margaret",
    "peggy": "margaret",
    "nancy": "ann",
    "nick": "nicholas",
    "phil": "philip",
    "ray": "raymond",
    "sam": "samuel",
    "sandy": "sandra",
    "steph": "stephanie",
    "terry": "terrence",
    "tim": "timothy",
    "wally": "walter",
}

# Build reverse: formal → set of nicknames
_FORMAL_TO_NICKNAMES: dict[str, set[str]] = defaultdict(set)
for _nick, _formal in _NICKNAME_TO_FORMAL.items():
    _FORMAL_TO_NICKNAMES[_formal].add(_nick)


def get_name_variants(name: str) -> set[str]:
    """Generate nickname/formal variants of a name.

    "Ken Lay" → {"ken lay", "kenneth lay"}
    "Kenneth Lay" → {"kenneth lay", "ken lay", "kenny lay"}
    """
    parts = name.lower().split()
    variants = {name.lower()}

    for i, part in enumerate(parts):
        new_parts = parts.copy()

        # nickname → formal
        if part in _NICKNAME_TO_FORMAL:
            new_parts[i] = _NICKNAME_TO_FORMAL[part]
            variants.add(" ".join(new_parts))

        # formal → all nicknames
        if part in _FORMAL_TO_NICKNAMES:
            for nick in _FORMAL_TO_NICKNAMES[part]:
                new_parts = parts.copy()
                new_parts[i] = nick
                variants.add(" ".join(new_parts))

    return variants


def strip_middle_initials(name: str) -> str:
    """Remove single-character parts (initials) from a name.

    "Steven J Kean" → "Steven Kean"
    "Steven J. Kean" → "Steven Kean"
    "J. K. Rowling" → "Rowling"  (edge case — all initials stripped)
    """
    parts = name.split()
    filtered = [p for p in parts if len(p.rstrip(".")) > 1]
    return " ".join(filtered) if filtered else name  # fallback to original if all stripped


def get_email_domain(email: str) -> str | None:
    """Extract domain from an email address."""
    if not email or "@" not in email:
        return None
    return email.split("@")[1].lower()


def get_last_name(name: str) -> str:
    """Extract the last word of a name for blocking."""
    parts = name.strip().split()
    return parts[-1].lower() if parts else ""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MergeCandidate:
    """A pair of entities that might be the same."""
    source_id: str          # entity to merge FROM (absorbed)
    target_id: str          # entity to merge INTO (survives)
    source_name: str
    target_name: str
    strategy: str           # "middle_initial", "nickname", "same_domain", "fuzzy"
    similarity: float       # rapidfuzz score (0-100) / 100
    confidence: float       # overall confidence considering all signals

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MergeOperation:
    """A recorded merge with snapshots for undo."""
    merge_id: str
    source_id: str
    target_id: str
    source_snapshot: dict      # full entity state BEFORE merge
    target_snapshot: dict      # full entity state BEFORE merge
    strategy: str
    confidence: float
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = "active"     # "active" or "undone"

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Fuzzy Matcher
# ---------------------------------------------------------------------------

class FuzzyMatcher:
    """Finds and applies fuzzy entity merges on top of Day 16 exact matching.

    Usage:
        matcher = FuzzyMatcher(entities, resolution_map)
        candidates = matcher.find_candidates()
        matcher.apply_merges(candidates)
        # or: matcher.apply_merges(candidates, auto_threshold=0.85)

        # Later, to undo:
        matcher.undo_merge("merge_id_here")
    """

    def __init__(
        self,
        entities: dict[str, dict],
        resolution_map: dict[str, str],
    ):
        # Deep copy so we don't modify the input
        self.entities = copy.deepcopy(entities)
        self.resolution_map = copy.deepcopy(resolution_map)
        self.merge_operations: list[MergeOperation] = []
        self._merged_ids: set[str] = set()  # entities already consumed by a merge

    # ------------------------------------------------------------------
    # Candidate finding
    # ------------------------------------------------------------------

    def find_candidates(self) -> list[MergeCandidate]:
        """Find all merge candidates using four strategies.

        Returns deduplicated candidates sorted by confidence (highest first).
        """
        people = {
            cid: e for cid, e in self.entities.items()
            if e["entity_type"] == "person"
        }
        orgs = {
            cid: e for cid, e in self.entities.items()
            if e["entity_type"] == "organization"
        }

        candidates = []
        candidates += self._find_middle_initial_candidates(people)
        candidates += self._find_nickname_candidates(people)
        candidates += self._find_same_domain_candidates(people)
        candidates += self._find_fuzzy_candidates(people)
        candidates += self._find_fuzzy_candidates(orgs)

        # Deduplicate: keep highest confidence for each (source, target) pair
        candidates = self._deduplicate(candidates)

        # Sort: highest confidence first
        candidates.sort(key=lambda c: c.confidence, reverse=True)

        logger.info("Found %d unique merge candidates", len(candidates))
        return candidates

    def _build_blocks(self, entities: dict[str, dict]) -> dict[str, list[str]]:
        """Group entity IDs by last name for efficient comparison."""
        blocks: dict[str, list[str]] = defaultdict(list)
        for cid, entity in entities.items():
            last = get_last_name(entity["canonical_name"])
            if last and len(last) > 1:  # skip single-char "last names"
                blocks[last].append(cid)
        return blocks

    def _find_middle_initial_candidates(
        self, entities: dict[str, dict]
    ) -> list[MergeCandidate]:
        """Find entities that match after stripping middle initials.

        "Steven J Kean" → stripped: "Steven Kean"
        If "Steven Kean" exists as another entity → candidate.
        """
        candidates = []
        # Build lookup: stripped_name_lower → list of entity IDs
        stripped_index: dict[str, list[str]] = defaultdict(list)
        for cid, entity in entities.items():
            stripped = strip_middle_initials(entity["canonical_name"])
            stripped_index[stripped.lower()].append(cid)

        for stripped_lower, cids in stripped_index.items():
            if len(cids) < 2:
                continue
            # Compare all pairs in this group
            for i in range(len(cids)):
                for j in range(i + 1, len(cids)):
                    e1 = entities[cids[i]]
                    e2 = entities[cids[j]]

                    # Check if they actually differ by middle initial
                    # (not just identical names that happen to group together)
                    if e1["canonical_name"].lower() == e2["canonical_name"].lower():
                        # Same name — either already merged or same-name-diff-email
                        # Handle via same_domain strategy instead
                        continue

                    # Check email domain compatibility
                    domain_match = self._check_domain_match(e1, e2)

                    confidence = 0.88 if domain_match else 0.82

                    # Source = fewer mentions (gets absorbed into the bigger entity)
                    source, target = self._pick_source_target(cids[i], cids[j])

                    candidates.append(MergeCandidate(
                        source_id=source,
                        target_id=target,
                        source_name=entities[source]["canonical_name"],
                        target_name=entities[target]["canonical_name"],
                        strategy="middle_initial",
                        similarity=fuzz.ratio(
                            e1["canonical_name"].lower(),
                            e2["canonical_name"].lower(),
                        ) / 100,
                        confidence=confidence,
                    ))

        logger.info("Middle initial strategy: %d candidates", len(candidates))
        return candidates

    def _find_nickname_candidates(
        self, entities: dict[str, dict]
    ) -> list[MergeCandidate]:
        """Find entities that match via nickname expansion.

        "Ken Lay" → expand to "Kenneth Lay"
        If "Kenneth Lay" exists → candidate.
        """
        candidates = []

        # Build lookup: lowered canonical name → entity ID
        name_to_id: dict[str, list[str]] = defaultdict(list)
        for cid, entity in entities.items():
            name_to_id[entity["canonical_name"].lower()].append(cid)

        # For each entity, generate name variants and check for matches
        seen_pairs: set[tuple[str, str]] = set()

        for cid, entity in entities.items():
            variants = get_name_variants(entity["canonical_name"])
            for variant in variants:
                if variant == entity["canonical_name"].lower():
                    continue  # skip self
                if variant in name_to_id:
                    for match_cid in name_to_id[variant]:
                        if match_cid == cid:
                            continue
                        pair = tuple(sorted([cid, match_cid]))
                        if pair in seen_pairs:
                            continue
                        seen_pairs.add(pair)

                        e_match = entities[match_cid]
                        domain_match = self._check_domain_match(entity, e_match)
                        confidence = 0.90 if domain_match else 0.85

                        source, target = self._pick_source_target(cid, match_cid)

                        candidates.append(MergeCandidate(
                            source_id=source,
                            target_id=target,
                            source_name=entities[source]["canonical_name"],
                            target_name=entities[target]["canonical_name"],
                            strategy="nickname",
                            similarity=fuzz.ratio(
                                entity["canonical_name"].lower(),
                                e_match["canonical_name"].lower(),
                            ) / 100,
                            confidence=confidence,
                        ))

        logger.info("Nickname strategy: %d candidates", len(candidates))
        return candidates

    def _find_same_domain_candidates(
        self, entities: dict[str, dict]
    ) -> list[MergeCandidate]:
        """Find entities with same name + same email domain.

        Catches the Kenneth Lay case: klay@enron.com vs kenneth.lay@enron.com
        Both named "Kenneth Lay", both @enron.com → definitely same person.
        """
        candidates = []
        blocks = self._build_blocks(entities)

        for block_key, cids in blocks.items():
            if len(cids) < 2:
                continue
            for i in range(len(cids)):
                for j in range(i + 1, len(cids)):
                    e1 = entities[cids[i]]
                    e2 = entities[cids[j]]

                    # Both must have emails
                    if not e1.get("emails") or not e2.get("emails"):
                        continue

                    # Check domain match
                    if not self._check_domain_match(e1, e2):
                        continue

                    # High name similarity required
                    sim = fuzz.ratio(
                        e1["canonical_name"].lower(),
                        e2["canonical_name"].lower(),
                    )
                    if sim < 80:
                        continue

                    source, target = self._pick_source_target(cids[i], cids[j])

                    candidates.append(MergeCandidate(
                        source_id=source,
                        target_id=target,
                        source_name=entities[source]["canonical_name"],
                        target_name=entities[target]["canonical_name"],
                        strategy="same_domain",
                        similarity=sim / 100,
                        confidence=0.92,  # same domain + high similarity = very confident
                    ))

        logger.info("Same-domain strategy: %d candidates", len(candidates))
        return candidates

    def _find_fuzzy_candidates(
        self, entities: dict[str, dict], threshold: float = 85.0
    ) -> list[MergeCandidate]:
        """General fuzzy matching within last-name blocks.

        Catches typos: "Klauber" vs "Klauberg", minor spelling variations.
        """
        candidates = []
        blocks = self._build_blocks(entities)
        seen_pairs: set[tuple[str, str]] = set()

        for block_key, cids in blocks.items():
            if len(cids) < 2:
                continue
            for i in range(len(cids)):
                for j in range(i + 1, len(cids)):
                    pair = tuple(sorted([cids[i], cids[j]]))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)

                    e1 = entities[cids[i]]
                    e2 = entities[cids[j]]

                    sim = fuzz.ratio(
                        e1["canonical_name"].lower(),
                        e2["canonical_name"].lower(),
                    )
                    if sim < threshold:
                        continue

                    # Skip exact matches (already handled by Day 16)
                    if sim == 100:
                        # Same name — only interesting if different emails
                        # (handled by same_domain strategy)
                        continue

                    domain_match = self._check_domain_match(e1, e2)
                    confidence = (sim / 100) * (1.05 if domain_match else 0.95)
                    confidence = min(confidence, 0.99)  # cap at 0.99

                    source, target = self._pick_source_target(cids[i], cids[j])

                    candidates.append(MergeCandidate(
                        source_id=source,
                        target_id=target,
                        source_name=entities[source]["canonical_name"],
                        target_name=entities[target]["canonical_name"],
                        strategy="fuzzy",
                        similarity=sim / 100,
                        confidence=round(confidence, 4),
                    ))

        logger.info("Fuzzy strategy: %d candidates", len(candidates))
        return candidates

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_domain_match(self, e1: dict, e2: dict) -> bool:
        """Check if two entities share an email domain."""
        domains1 = {get_email_domain(em) for em in e1.get("emails", []) if em}
        domains2 = {get_email_domain(em) for em in e2.get("emails", []) if em}
        domains1.discard(None)
        domains2.discard(None)
        if not domains1 or not domains2:
            return False
        return bool(domains1 & domains2)

    def _pick_source_target(self, cid1: str, cid2: str) -> tuple[str, str]:
        """Source = fewer mentions (gets absorbed). Target = more mentions (survives)."""
        e1 = self.entities[cid1]
        e2 = self.entities[cid2]
        if e1["mention_count"] <= e2["mention_count"]:
            return cid1, cid2
        return cid2, cid1

    def _deduplicate(self, candidates: list[MergeCandidate]) -> list[MergeCandidate]:
        """Keep only the highest-confidence candidate for each entity pair."""
        best: dict[tuple[str, str], MergeCandidate] = {}
        for c in candidates:
            pair = tuple(sorted([c.source_id, c.target_id]))
            if pair not in best or c.confidence > best[pair].confidence:
                best[pair] = c
        return list(best.values())

    # ------------------------------------------------------------------
    # Merging
    # ------------------------------------------------------------------

    def apply_merges(
        self, candidates: list[MergeCandidate], auto_threshold: float = 0.85
    ) -> int:
        """Apply merges for candidates above the confidence threshold.

        Returns the number of merges applied.
        """
        applied = 0

        for candidate in candidates:
            if candidate.confidence < auto_threshold:
                continue

            # Skip if either entity was already consumed by a previous merge
            if candidate.source_id in self._merged_ids:
                continue
            if candidate.target_id in self._merged_ids:
                continue

            # Skip if entities no longer exist (consumed by earlier merge this run)
            if candidate.source_id not in self.entities:
                continue
            if candidate.target_id not in self.entities:
                continue

            self._merge(candidate)
            applied += 1

        logger.info(
            "Applied %d merges (threshold: %.2f)", applied, auto_threshold
        )
        return applied

    def _merge(self, candidate: MergeCandidate) -> None:
        """Merge source entity into target entity with full audit trail."""
        source = self.entities[candidate.source_id]
        target = self.entities[candidate.target_id]

        # Snapshot BEFORE merge (for undo)
        operation = MergeOperation(
            merge_id=str(uuid.uuid4())[:12],
            source_id=candidate.source_id,
            target_id=candidate.target_id,
            source_snapshot=copy.deepcopy(source),
            target_snapshot=copy.deepcopy(target),
            strategy=candidate.strategy,
            confidence=candidate.confidence,
        )

        # Perform merge: transfer everything from source to target
        if isinstance(target["aliases"], list):
            target["aliases"] = set(target["aliases"])
        if isinstance(source["aliases"], list):
            source["aliases"] = set(source["aliases"])

        target["aliases"] = list(set(target["aliases"]) | set(source["aliases"]))
        target["emails"] = list(set(target.get("emails", [])) | set(source.get("emails", [])))
        target["mention_count"] = target.get("mention_count", 0) + source.get("mention_count", 0)

        # Re-select canonical name (most mentioned variant)
        # Simple heuristic: keep the longer name or the current target name
        if len(source.get("canonical_name", "")) > len(target.get("canonical_name", "")):
            # Only switch if source name is substantially longer
            target["canonical_name"] = source["canonical_name"]

        # Update resolution map: all names pointing to source now point to target
        for name, cid in list(self.resolution_map.items()):
            if cid == candidate.source_id:
                self.resolution_map[name] = candidate.target_id

        # Remove source entity
        del self.entities[candidate.source_id]
        self._merged_ids.add(candidate.source_id)

        # Record operation
        self.merge_operations.append(operation)

        logger.debug(
            "Merged '%s' into '%s' (%s, confidence=%.2f)",
            source.get("canonical_name"), target.get("canonical_name"),
            candidate.strategy, candidate.confidence,
        )

    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------

    def undo_merge(self, merge_id: str) -> bool:
        """Undo a specific merge operation.

        Restores both entities to their pre-merge state and
        updates the resolution map accordingly.

        Returns True if successful, False if merge_id not found
        or already undone.
        """
        operation = None
        for op in self.merge_operations:
            if op.merge_id == merge_id:
                operation = op
                break

        if operation is None:
            logger.warning("Merge ID '%s' not found", merge_id)
            return False

        if operation.status == "undone":
            logger.warning("Merge ID '%s' already undone", merge_id)
            return False

        # Restore source entity from snapshot
        self.entities[operation.source_id] = copy.deepcopy(operation.source_snapshot)

        # Restore target entity from snapshot (removes merged aliases/emails)
        self.entities[operation.target_id] = copy.deepcopy(operation.target_snapshot)

        # Restore resolution map: source aliases point back to source
        source_aliases = operation.source_snapshot.get("aliases", [])
        for alias in source_aliases:
            self.resolution_map[alias] = operation.source_id

        # Restore target aliases in map too
        target_aliases = operation.target_snapshot.get("aliases", [])
        for alias in target_aliases:
            self.resolution_map[alias] = operation.target_id

        # Unmark source as merged
        self._merged_ids.discard(operation.source_id)

        operation.status = "undone"

        logger.info(
            "Undone merge '%s': restored '%s' from '%s'",
            merge_id,
            operation.source_snapshot.get("canonical_name"),
            self.entities[operation.target_id].get("canonical_name"),
        )
        return True

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return fuzzy matching statistics."""
        active = [op for op in self.merge_operations if op.status == "active"]
        undone = [op for op in self.merge_operations if op.status == "undone"]

        by_strategy = defaultdict(int)
        for op in active:
            by_strategy[op.strategy] += 1

        return {
            "total_merges_applied": len(active),
            "total_merges_undone": len(undone),
            "merges_by_strategy": dict(by_strategy),
            "entities_remaining": len(self.entities),
            "people_remaining": sum(
                1 for e in self.entities.values() if e["entity_type"] == "person"
            ),
            "orgs_remaining": sum(
                1 for e in self.entities.values() if e["entity_type"] == "organization"
            ),
        }

    def get_merge_operations(self) -> list[dict]:
        return [op.to_dict() for op in self.merge_operations]