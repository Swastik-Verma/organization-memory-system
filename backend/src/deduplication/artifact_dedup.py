"""
Artifact deduplication — detect exact and near-duplicate emails.

Exact duplicates:  SHA-256 hash of whitespace-normalized body.
Near-duplicates:   Cosine similarity of sentence-transformer embeddings,
                   computed on noise-stripped (original) content.

Downstream usage:  During Neo4j ingestion, skip any message_id that
                   appears in `duplicate_ids` — only load the primary.

Why this matters:  A forwarded email has a different Message-ID than the
original, but nearly identical content. Extracting from both produces
duplicate claims in the graph (same person, same relationship, same
evidence quote). Deduplicating at the email level prevents this.
"""

import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from sentence_transformers import SentenceTransformer

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DuplicateGroup:
    """A cluster of emails that are duplicates of each other."""
    primary_id: str                # message_id of the email to keep
    duplicate_ids: list[str]       # message_ids to skip
    method: str                    # "exact_hash" or "near_duplicate"
    similarity: float              # 1.0 for exact, cosine sim for near-dupes
    reason: str                    # human-readable explanation

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ArtifactDedupResult:
    """Full result of artifact deduplication."""
    exact_groups: list[DuplicateGroup] = field(default_factory=list)
    near_groups: list[DuplicateGroup] = field(default_factory=list)

    @property
    def all_groups(self) -> list[DuplicateGroup]:
        return self.exact_groups + self.near_groups

    @property
    def duplicate_ids(self) -> set[str]:
        """Flat set of all message_ids to SKIP during ingestion.
        O(1) lookup: `if msg_id in result.duplicate_ids: skip`."""
        ids = set()
        for group in self.all_groups:
            ids.update(group.duplicate_ids)
        return ids

    @property
    def primary_ids(self) -> set[str]:
        """Set of all primary message_ids (the ones to KEEP)."""
        return {g.primary_id for g in self.all_groups}

    def summary(self) -> dict:
        dup_ids = self.duplicate_ids
        return {
            "exact_duplicate_groups": len(self.exact_groups),
            "near_duplicate_groups": len(self.near_groups),
            "total_groups": len(self.all_groups),
            "total_duplicates_to_skip": len(dup_ids),
            "total_primaries": len(self.primary_ids),
        }

    def to_dict(self) -> dict:
        return {
            "summary": self.summary(),
            "exact_groups": [g.to_dict() for g in self.exact_groups],
            "near_groups": [g.to_dict() for g in self.near_groups],
            "duplicate_ids": sorted(self.duplicate_ids),
        }


# ---------------------------------------------------------------------------
# Exact dedup via content hash
# ---------------------------------------------------------------------------

def normalize_for_hash(body: str) -> str:
    """Collapse all whitespace, lowercase, strip.

    Two emails with the same words but different line-wrapping
    (common in the Enron corpus, which hard-wraps at ~76 chars)
    produce the same normalized string and therefore the same hash.
    """
    return " ".join(body.split()).lower().strip()


def find_exact_duplicates(emails: list[dict]) -> list[DuplicateGroup]:
    """Group emails with identical body content by SHA-256 hash.

    Args:
        emails: list of dicts, each with at least 'message_id' and 'body'.

    Returns:
        List of DuplicateGroups. Only groups with 2+ members are returned.
    """
    hash_to_entries: dict[str, list[dict]] = defaultdict(list)

    for email in emails:
        body = email.get("body") or ""
        normalized = normalize_for_hash(body)
        h = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        hash_to_entries[h].append(email)

    groups = []
    for h, entries in hash_to_entries.items():
        if len(entries) < 2:
            continue

        # Pick the primary: earliest date, then longest body, then first ID
        sorted_entries = sorted(
            entries,
            key=lambda e: (
                e.get("date") or "9999-12-31",  # null dates sort last
                -len(e.get("body") or ""),
                e.get("message_id", ""),
            ),
        )

        primary = sorted_entries[0]
        duplicates = sorted_entries[1:]

        groups.append(DuplicateGroup(
            primary_id=primary["message_id"],
            duplicate_ids=[d["message_id"] for d in duplicates],
            method="exact_hash",
            similarity=1.0,
            reason=f"Identical normalized body (SHA-256: {h[:12]}…)",
        ))

    logger.info(
        "Exact dedup: %d groups found (%d duplicate emails)",
        len(groups),
        sum(len(g.duplicate_ids) for g in groups),
    )
    return groups


# ---------------------------------------------------------------------------
# Near-duplicate detection via embedding similarity
# ---------------------------------------------------------------------------

def _select_primary(entries: list[dict]) -> tuple[dict, list[dict]]:
    """Pick the primary email from a near-duplicate cluster.

    Same logic as exact dedup: earliest date → longest body → first ID.
    """
    sorted_entries = sorted(
        entries,
        key=lambda e: (
            e.get("date") or "9999-12-31",
            -len(e.get("original_content") or e.get("body") or ""),
            e.get("message_id", ""),
        ),
    )
    return sorted_entries[0], sorted_entries[1:]


def find_near_duplicates(
    emails: list[dict],
    model_name: str = "all-MiniLM-L6-v2",
    threshold: float = 0.95,
    chunk_size: int = 500,
) -> list[DuplicateGroup]:
    """Find near-duplicate emails via embedding cosine similarity.

    Uses chunked computation to stay within 8GB RAM.
    A 10k × 384 embedding matrix is ~15MB.
    Each chunk produces a (chunk_size × 10k) similarity slice at ~20MB.

    Args:
        emails:     list of dicts with 'message_id' and 'body'
                    (and optionally 'original_content' for noise-stripped text).
        model_name: sentence-transformers model. Stick to all-MiniLM-L6-v2.
        threshold:  cosine similarity cutoff. 0.95 catches forwards/cross-posts
                    without flagging merely-topically-similar emails.
        chunk_size: rows per similarity chunk. 500 keeps memory under ~20MB/chunk.

    Returns:
        List of DuplicateGroups for near-duplicate clusters.
    """
    

    if len(emails) < 2:
        return []

    logger.info("Loading sentence-transformer model '%s'…", model_name)
    model = SentenceTransformer(model_name)

    # Prefer noise-stripped content; fall back to raw body
    texts = [
        e.get("original_content") or e.get("body") or ""
        for e in emails
    ]
    ids = [e["message_id"] for e in emails]

    logger.info("Embedding %d email bodies…", len(texts))
    embeddings = model.encode(
        texts,
        show_progress_bar=True,
        batch_size=64,
        normalize_embeddings=True,  # L2-normalize → dot product = cosine sim
    )
    # embeddings is now (N, 384), each row unit-length

    # ------------------------------------------------------------------
    # Chunked pairwise similarity + Union-Find grouping
    # ------------------------------------------------------------------
    # Why Union-Find? If A~B and B~C, then {A,B,C} should be one group.
    # Union-Find handles this transitivity efficiently.
    # ------------------------------------------------------------------

    n = len(ids)
    parent = list(range(n))
    rank = [0] * n

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # path compression
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px == py:
            return
        # union by rank
        if rank[px] < rank[py]:
            px, py = py, px
        parent[py] = px
        if rank[px] == rank[py]:
            rank[px] += 1

    pair_count = 0

    logger.info("Computing pairwise similarities in chunks of %d…", chunk_size)
    for start in range(0, n, chunk_size):
        end = min(start + chunk_size, n)
        chunk = embeddings[start:end]  # (chunk_size, 384)

        # Only compute similarity with indices > start to avoid double-counting
        # For the upper triangle: compare chunk rows against all rows with index > row
        sims = chunk @ embeddings.T  # (chunk_size, N)

        for local_idx in range(end - start):
            global_idx = start + local_idx
            # Only look at j > global_idx (upper triangle)
            for j in range(global_idx + 1, n):
                if sims[local_idx, j] >= threshold:
                    union(global_idx, j)
                    pair_count += 1

    logger.info("Found %d near-duplicate pairs above %.2f threshold", pair_count, threshold)

    # Build clusters from Union-Find
    clusters: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)

    groups = []
    for root, members in clusters.items():
        if len(members) < 2:
            continue

        member_emails = [emails[i] for i in members]
        primary, duplicates = _select_primary(member_emails)

        # Compute average pairwise similarity for the group
        member_embeds = embeddings[members]
        if len(members) <= 10:
            # Small group: compute all pairwise
            sim_matrix = member_embeds @ member_embeds.T
            # Extract upper triangle (excluding diagonal)
            upper_sims = [
                sim_matrix[i, j]
                for i in range(len(members))
                for j in range(i + 1, len(members))
            ]
            avg_sim = float(np.mean(upper_sims)) if upper_sims else threshold
        else:
            avg_sim = threshold  # for large groups, skip full pairwise

        groups.append(DuplicateGroup(
            primary_id=primary["message_id"],
            duplicate_ids=[d["message_id"] for d in duplicates],
            method="near_duplicate",
            similarity=round(avg_sim, 4),
            reason=f"Near-duplicate content (avg cosine similarity: {avg_sim:.4f})",
        ))

    logger.info(
        "Near-duplicate dedup: %d groups found (%d duplicate emails)",
        len(groups),
        sum(len(g.duplicate_ids) for g in groups),
    )
    return groups


# ---------------------------------------------------------------------------
# Combined pipeline
# ---------------------------------------------------------------------------

def run_artifact_dedup(
    emails: list[dict],
    near_dup_threshold: float = 0.95,
    skip_near_duplicates: bool = False,
) -> ArtifactDedupResult:
    """Run full artifact deduplication: exact hash + near-duplicate detection.

    Args:
        emails:               list of parsed email dicts (need message_id, body).
        near_dup_threshold:   cosine similarity threshold for near-duplicates.
        skip_near_duplicates: if True, skip the embedding step (useful for testing
                              or when you only want exact dedup).
    """
    result = ArtifactDedupResult()

    # Phase 1: exact duplicates
    result.exact_groups = find_exact_duplicates(emails)

    # Phase 2: near-duplicates (skip emails already caught by exact dedup)
    if not skip_near_duplicates:
        exact_dup_ids = set()
        for g in result.exact_groups:
            exact_dup_ids.update(g.duplicate_ids)

        remaining = [e for e in emails if e["message_id"] not in exact_dup_ids]
        result.near_groups = find_near_duplicates(
            remaining, threshold=near_dup_threshold
        )

    return result