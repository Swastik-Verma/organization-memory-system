// Composes a readable entity-to-entity graph out of two backend endpoints.
//
// ── Why this file exists (Day 41 finding, user-approved approach) ─────────────────────
// GET /api/graph/{id}/subgraph cannot return an entity-to-entity edge at any depth. A
// claim is stored as (:Person)<-[:SUBJECT]-(:Claim)-[:OBJECT]->(:Person), so the raw
// endpoint's edges are the plumbing types (SUBJECT / OBJECT / SENT_BY / SENT_TO / ...),
// never the claim type. Measured live against Sally Beck (2,244 total edges):
//
//   depth=1&limit=200 → 201 nodes: 200 Claim nodes + 1 Person. Zero entity-to-entity edges.
//   depth=2&limit=200 →  87 nodes, 112 edges, ALL of type PARTY, zero Claim nodes — the
//                        route's Cypher LIMITs before it has enumerated the claim paths,
//                        so depth=2 returns an arbitrary, unrepresentative slice.
//
// GET /api/entities/{id}/claims, by contrast, returns exactly the edge list the explorer
// needs: subject_id, object_id, claim_type, confidence, mention_count, and (since the
// Day 41 follow-up backend change) subject_mention_count / object_mention_count — the real
// per-ENTITY mention counts, which is what node tooltips and node radius display.
//
// So the graph is built from BOTH:
//   1. /api/entities/{id}/claims  → person/org edges carrying the 5 claim types
//   2. /api/graph/{id}/subgraph   → Deal (PARTY) and Decision (MADE_BY / AFFECTS)
//                                   neighbours, with Claim and Message nodes discarded
//
// Together these give the 8 relationship types the UI renders. No backend change involved;
// both calls are quota-free (Neo4j only, no LLM).
//
// ── Known limitation: structural neighbours are best-effort ───────────────────────────
// /api/graph/{id}/subgraph caps at limit=200 and applies no server-side relationship-type
// filter, and its Cypher returns rows in Neo4j's own enumeration order. For an entity with
// more than 200 edges, whichever types happen to be enumerated first fill the response and
// the rest are truncated. Measured:
//
//   Sally Beck  (2,244 edges) → all 200 rows are SUBJECT/OBJECT, so her 83 PARTY and 867
//                               AFFECTS/MADE_BY edges never arrive: no Deal or Decision
//                               node appears in her graph.
//   org:enron                 → all 200 rows are AFFECTS, so 8 Decision nodes DO appear.
//   deal:amtrak-…, Kay Mann   → few edges overall, everything arrives.
//
// This is not fixable from the frontend (the limit is already at its maximum and there is no
// type filter to pass). It degrades gracefully rather than breaking: the claim edges come
// from /claims, which has no limit at all, so the core entity-to-entity graph is always
// complete — only the Deal/Decision garnish is hit-or-miss on very busy entities. A backend
// change (a type filter on the subgraph route) would close it; CLAUDE.md §5, not made here.
//
// ── Neighbour caps ────────────────────────────────────────────────────────────────────
// A single busy person can have 250+ claims. Rendering all of them produces an unreadable
// hairball and a slow force simulation, so each fetch keeps the strongest N counterparts.
// Ranking is by best confidence, then by how many claims connect them to the centre.

import { fetchEntityClaims, fetchSubgraph } from '@/lib/api'
import { STRUCTURAL_RELATIONSHIP_TYPES, isSymmetricRelationship } from '@/lib/relationshipTypes'
import type { ClaimResult } from '@/types/entity'
import type { GraphEdge, GraphNode, SubgraphResponse } from '@/types/graph'

/** Max distinct person/org counterparts kept from the claims call, per fetch. */
export const MAX_CLAIM_NEIGHBOURS = 20
/** Max distinct Deal/Decision neighbours kept from the subgraph call, per fetch. */
export const MAX_STRUCTURAL_NEIGHBOURS = 8

/** Entity ids are prefixed by type: person: / org: / deal: / decision: / claim: / evidence:
 *  The claims endpoint gives ids and names but no type, so the type is read off the prefix.
 *  Verified against the live graph — every Person, Organization, Deal and Decision id
 *  follows this scheme. */
export function entityTypeFromId(id: string): string {
  const prefix = id.split(':')[0]
  if (prefix === 'org') return 'organization'
  if (prefix === 'person' || prefix === 'deal' || prefix === 'decision') return prefix
  return 'unknown'
}

/** Node types that belong on the canvas. Anything else the raw subgraph returns (notably
 *  `claim`, and Message nodes) is internal structure, not something a user explores. */
const RENDERABLE_NODE_TYPES = new Set(['person', 'organization', 'deal', 'decision'])

/**
 * Identity of an edge.
 *
 * For a SYMMETRIC relationship the endpoints are sorted first, so "A works_with B" and
 * "B works_with A" — which are the same fact, recorded twice because two separate claims
 * were extracted from two different emails — collapse into one edge instead of two lines
 * drawn on top of each other in opposite directions.
 *
 * Asymmetric relationships keep their direction: "A reports_to B" and "B reports_to A" are
 * genuinely different assertions and both deserve to be visible.
 */
export function edgeKey(source: string, target: string, type: string): string {
  if (isSymmetricRelationship(type)) {
    const [a, b] = [source, target].sort()
    return `${a}::${type}::${b}`
  }
  return `${source}::${type}::${target}`
}

interface NeighbourAccumulator {
  id: string
  name: string
  /** Best confidence across every claim linking this neighbour to the centre. */
  bestConfidence: number
  /** The entity's OWN mention_count, straight from the claims response. This is the same
   *  number GET /api/entities/{id} reports, so a node's tooltip agrees with its detail page. */
  mentionCount: number
  /** Total claim-level mention_count across the shared claims. Used ONLY to rank which
   *  neighbours make the cut — never displayed, and never confused with mentionCount. */
  rankWeight: number
  claims: ClaimResult[]
}

/**
 * Collapses a claims list into ranked counterpart entities. A claim whose subject and
 * object are the same entity (self-loop) is dropped — it carries no relationship and would
 * render as a degenerate edge.
 */
function rankNeighbours(claims: ClaimResult[], centreId: string): NeighbourAccumulator[] {
  const byId = new Map<string, NeighbourAccumulator>()

  for (const claim of claims) {
    const isSubject = claim.subject_id === centreId
    const otherId = isSubject ? claim.object_id : claim.subject_id
    const otherName = isSubject ? claim.object_name : claim.subject_name
    // The neighbour sits on whichever side the centre is NOT on, so its entity mention
    // count is the opposite side's field.
    const otherMentionCount = isSubject ? claim.object_mention_count : claim.subject_mention_count
    if (!otherId || otherId === centreId) continue

    let acc = byId.get(otherId)
    if (!acc) {
      acc = {
        id: otherId,
        name: otherName || otherId,
        bestConfidence: 0,
        mentionCount: 0,
        rankWeight: 0,
        claims: [],
      }
      byId.set(otherId, acc)
    }
    acc.bestConfidence = Math.max(acc.bestConfidence, claim.confidence)
    // Every claim naming this entity reports the same entity-level count, so max() just
    // takes that value while tolerating a 0 from an older backend or a missing endpoint.
    acc.mentionCount = Math.max(acc.mentionCount, otherMentionCount || 0)
    acc.rankWeight += claim.mention_count || 1
    acc.claims.push(claim)
  }

  return Array.from(byId.values()).sort(
    (a, b) =>
      b.bestConfidence - a.bestConfidence ||
      b.rankWeight - a.rankWeight ||
      a.name.localeCompare(b.name),
  )
}

/**
 * Fetches one entity's neighbourhood as a renderable subgraph.
 *
 * The two backend calls run in parallel and are independently fault-tolerant: if the
 * subgraph call fails (e.g. the centre is reachable through claims but 404s on the graph
 * route) the claim edges are still returned, and vice versa. Only a total failure of both
 * rejects — a partial graph is far more useful than an error screen.
 */
export async function fetchEntityGraph(
  entityId: string,
  options: { signal?: AbortSignal } = {},
): Promise<SubgraphResponse> {
  const [claimsResult, subgraphResult] = await Promise.allSettled([
    fetchEntityClaims(entityId, undefined, options),
    fetchSubgraph(entityId, 1, 200, options),
  ])

  if (claimsResult.status === 'rejected' && subgraphResult.status === 'rejected') {
    throw claimsResult.reason
  }

  const nodes = new Map<string, GraphNode>()
  const edges = new Map<string, GraphEdge>()

  // ---- Centre node -------------------------------------------------------------------
  // The subgraph response is the preferred source for the centre's label, type and
  // mention_count. The claims response can now supply the count too (see the fallback
  // below), so a failed subgraph call no longer forces a fabricated 0.
  const rawSubgraph = subgraphResult.status === 'fulfilled' ? subgraphResult.value : null
  const rawCentre = rawSubgraph?.nodes.find((n) => n.id === entityId)
  if (rawCentre) {
    nodes.set(entityId, { ...rawCentre })
  }

  // ---- Claim-derived person/org edges -------------------------------------------------
  if (claimsResult.status === 'fulfilled') {
    const claims = claimsResult.value.claims
    const neighbours = rankNeighbours(claims, entityId).slice(0, MAX_CLAIM_NEIGHBOURS)
    const kept = new Set(neighbours.map((n) => n.id))

    // The centre may be absent above when the subgraph call failed — recover its name AND
    // its real mention_count from any claim it appears in, rather than dropping it from its
    // own graph or showing a fabricated 0.
    if (!nodes.has(entityId)) {
      const anyClaim = claims[0]
      const centreIsSubject = anyClaim?.subject_id === entityId
      const label = anyClaim ? (centreIsSubject ? anyClaim.subject_name : anyClaim.object_name) : entityId
      const centreMentionCount = anyClaim
        ? (centreIsSubject ? anyClaim.subject_mention_count : anyClaim.object_mention_count) || 0
        : 0
      nodes.set(entityId, {
        id: entityId,
        label: label || entityId,
        type: entityTypeFromId(entityId),
        mention_count: centreMentionCount,
      })
    }

    for (const neighbour of neighbours) {
      nodes.set(neighbour.id, {
        id: neighbour.id,
        label: neighbour.name,
        type: entityTypeFromId(neighbour.id),
        // The entity's real mention_count, as reported by /api/entities/{id}/claims'
        // subject_mention_count / object_mention_count. A neighbour node therefore shows
        // the same figure as its own detail page, and node radius encodes real prominence.
        mention_count: neighbour.mentionCount,
      })

      // One edge per (direction, claim_type) pair. Two people can genuinely hold several
      // different relationships (works_with AND requests_from AND informs), and collapsing
      // those into one line would discard real information — but repeats of the SAME type
      // are merged into a single edge carrying a claim_count.
      const merged = new Map<string, { claim: ClaimResult; count: number; confidence: number }>()
      for (const claim of neighbour.claims) {
        if (!kept.has(claim.subject_id === entityId ? claim.object_id : claim.subject_id)) continue
        const key = edgeKey(claim.subject_id, claim.object_id, claim.claim_type)
        const existing = merged.get(key)
        if (existing) {
          existing.count += 1
          existing.confidence = Math.max(existing.confidence, claim.confidence)
        } else {
          merged.set(key, { claim, count: 1, confidence: claim.confidence })
        }
      }

      for (const [key, { claim, count, confidence }] of merged) {
        const existing = edges.get(key)
        if (existing) {
          // The same symmetric edge can be reached from both of its endpoints as separate
          // neighbours in this same response — fold the counts together rather than
          // keeping whichever arrived first.
          existing.claim_count = (existing.claim_count ?? 0) + count
          existing.confidence = Math.max(existing.confidence ?? 0, confidence)
          continue
        }
        // Symmetric edges are emitted with sorted endpoints so that the same relationship,
        // reached from either of its two entities in two different fetches, produces an
        // identical edge object rather than two mirror-image duplicates on the canvas.
        const [source, target] = isSymmetricRelationship(claim.claim_type)
          ? [claim.subject_id, claim.object_id].sort()
          : [claim.subject_id, claim.object_id]
        edges.set(key, {
          source,
          target,
          type: claim.claim_type,
          claim_type: claim.claim_type,
          confidence,
          claim_count: count,
        })
      }
    }
  }

  // ---- Structural Deal / Decision neighbours ------------------------------------------
  if (rawSubgraph) {
    const rawNodesById = new Map(rawSubgraph.nodes.map((n) => [n.id, n]))
    let added = 0

    for (const edge of rawSubgraph.edges) {
      if (added >= MAX_STRUCTURAL_NEIGHBOURS) break

      const displayType = STRUCTURAL_RELATIONSHIP_TYPES[edge.type]
      if (!displayType) continue // SUBJECT / OBJECT / SENT_BY / ... — plumbing, not shown

      const otherId = edge.source === entityId ? edge.target : edge.source
      if (otherId === entityId) continue

      const rawNode = rawNodesById.get(otherId)
      if (!rawNode || !RENDERABLE_NODE_TYPES.has(rawNode.type)) continue

      if (!nodes.has(otherId)) {
        nodes.set(otherId, { ...rawNode })
        added += 1
      }

      const key = edgeKey(edge.source, edge.target, displayType)
      if (!edges.has(key)) {
        edges.set(key, {
          source: edge.source,
          target: edge.target,
          type: displayType,
          claim_type: null,
          // The raw endpoint never populates confidence for structural edges.
          confidence: null,
          claim_count: null,
        })
      }
    }
  }

  // A node with no surviving edge would float unanchored; drop any edge whose endpoints
  // didn't both make the cut, then drop nodes left with nothing (except the centre).
  for (const [key, edge] of edges) {
    if (!nodes.has(edge.source) || !nodes.has(edge.target)) edges.delete(key)
  }

  return {
    center_id: entityId,
    nodes: Array.from(nodes.values()),
    edges: Array.from(edges.values()),
  }
}
