import type { GraphEdge, GraphNode, GraphSearchResult, SubgraphResponse } from '@/types/graph'

// Mock subgraph fixtures matching the real SubgraphResponse shape
// (backend/src/api/models.py / backend/src/api/routes/graph.py). Used to develop the
// graph explorer without touching the live /api/graph/* endpoints — see CLAUDE.md §9 and
// the Day 38 task brief. Real integration happens on Day 41.
//
// Known Day 41 gotcha (found while reading the backend route to build these fixtures):
// the real graph does NOT have direct Person→Person / Person→Org edges for claims. Claims
// are their own Neo4j nodes — relationships are modeled as
// Person <-[:SUBJECT]- Claim -[:OBJECT]-> Person (see backend/src/graph/loader.py).
// So a real depth=1 subgraph around a Person will surface neighboring Claim nodes (not
// other People/Orgs directly) — reaching another Person takes depth=2. These mocks instead
// show direct entity-to-entity edges (matching the day brief's example shape and what's
// actually useful to look at), so the visual topology here won't match the real API
// response until the graph explorer is adapted for the Claim-intermediary structure, or
// the UI is told to always request depth=2 and collapse the Claim hop. Flag this before
// starting Day 41.
//
// ---------------------------------------------------------------------------------------
// ENTITY IDENTITY RULE (this file previously had a real bug here — twice):
//
// Every entity has exactly ONE canonical ID and ONE canonical name, declared once in the
// ENTITIES registry below. Fixtures never repeat a name literal — they reference an entity
// by ID (`node(SALLY_BECK)`) and the label/type/mention_count are looked up. This makes it
// structurally impossible for the same entity to appear under two names, which is what
// went wrong before: an earlier version of this file generated placeholder neighbours named
// "{label} — Contact A" / "— Contact B" with fabricated IDs for any entity that had no
// fixture of its own, so expanding e.g. "West Trading Desk" or "Finance" produced two fake
// nodes that read as duplicates of the entity you just clicked.
//
// Two invariants keep it fixed, both enforced by validateMockIntegrity() below:
//   1. Every entity referenced by any fixture has its own fixture, so expanding any visible
//      node returns real, consistently-identified data — never a synthetic placeholder.
//   2. No two IDs share a name, and no ID has more than one name.
// ---------------------------------------------------------------------------------------

// ---- Canonical entity IDs (type:slug:email-slug, per CLAUDE.md §8.1) ----

const SALLY_BECK = 'person:beck-sally:sally-beck-at-enron-com'
const JOHN_LAVORATO = 'person:lavorato-john:john-lavorato-at-enron-com'
const LOUISE_KITCHEN = 'person:kitchen-louise:louise-kitchen-at-enron-com'
const FLETCHER_STURM = 'person:sturm-fletcher:fletcher-sturm-at-enron-com'
const KENNETH_LAY = 'person:lay-kenneth:kenneth-lay-at-enron-com'
const JOHN_ZUFFERLI = 'person:zufferli-john:john-zufferli-at-enron-com'

const WEST_TRADING_DESK = 'org:west-trading-desk:west-trading-desk'
const ENRON_AMERICA = 'org:enron-america:enron-america'
const ENRON_LEGAL = 'org:enron-legal:enron-legal'
const FINANCE = 'org:finance:finance'
const GLOBAL_CROSSING_LTD = 'org:global-crossing-ltd:global-crossing-ltd'

const GLOBAL_CROSSING_DEAL = 'deal:global-crossing-transaction:global-crossing-transaction'

const APPROVE_GC_DEAL = 'decision:approve-global-crossing-deal:approve-global-crossing-deal'
const AUGUST_REORG = 'decision:august-2001-reorganization:august-2001-reorganization'

// ---- Canonical entity definitions — the single source of truth for name/type/mentions ----

interface EntityDef {
  label: string
  type: string
  mention_count: number
}

const ENTITIES: Record<string, EntityDef> = {
  [SALLY_BECK]: { label: 'Sally Beck', type: 'person', mention_count: 42 },
  [JOHN_LAVORATO]: { label: 'John Lavorato', type: 'person', mention_count: 28 },
  [LOUISE_KITCHEN]: { label: 'Louise Kitchen', type: 'person', mention_count: 35 },
  [FLETCHER_STURM]: { label: 'Fletcher Sturm', type: 'person', mention_count: 12 },
  [KENNETH_LAY]: { label: 'Kenneth Lay', type: 'person', mention_count: 82 },
  [JOHN_ZUFFERLI]: { label: 'John Zufferli', type: 'person', mention_count: 19 },
  [WEST_TRADING_DESK]: { label: 'West Trading Desk', type: 'organization', mention_count: 8 },
  [ENRON_AMERICA]: { label: 'Enron America', type: 'organization', mention_count: 78 },
  [ENRON_LEGAL]: { label: 'Enron Legal', type: 'organization', mention_count: 22 },
  [FINANCE]: { label: 'Finance', type: 'organization', mention_count: 9 },
  [GLOBAL_CROSSING_LTD]: { label: 'Global Crossing Ltd', type: 'organization', mention_count: 45 },
  [GLOBAL_CROSSING_DEAL]: {
    label: 'Global Crossing Transaction',
    type: 'deal',
    mention_count: 15,
  },
  [APPROVE_GC_DEAL]: {
    label: 'Approve Global Crossing Deal',
    type: 'decision',
    mention_count: 6,
  },
  [AUGUST_REORG]: {
    label: 'August 2001 Reorganization',
    type: 'decision',
    mention_count: 55,
  },
}

/**
 * Builds a GraphNode from the canonical registry. Fixtures must use this rather than
 * spelling out a label — that's what guarantees one name per entity everywhere.
 */
function node(id: string): GraphNode {
  const def = ENTITIES[id]
  if (!def) {
    throw new Error(`graphMocks: no canonical entity registered for id "${id}"`)
  }
  return { id, label: def.label, type: def.type, mention_count: def.mention_count }
}

function edge(source: string, target: string, claimType: string, claim_count: number): GraphEdge {
  return { source, target, type: claimType, claim_type: claimType, confidence: null, claim_count }
}

// ---- Fixtures ----
//
// Every entity in ENTITIES has a fixture here, so any node the user can see is expandable
// to real data. Edges that also appear in another fixture are intentional: they're what
// makes expanding a node exercise the merge/dedup path (same source/type/target ⇒ same
// edgeKey in GraphExplorerPage, so the duplicate is skipped rather than double-drawn).

const SALLY_BECK_SUBGRAPH: SubgraphResponse = {
  center_id: SALLY_BECK,
  nodes: [
    node(SALLY_BECK),
    node(JOHN_LAVORATO),
    node(LOUISE_KITCHEN),
    node(FLETCHER_STURM),
    node(WEST_TRADING_DESK),
    node(ENRON_AMERICA),
    node(AUGUST_REORG),
  ],
  edges: [
    edge(SALLY_BECK, JOHN_LAVORATO, 'reports_to', 3),
    edge(SALLY_BECK, LOUISE_KITCHEN, 'works_with', 5),
    edge(SALLY_BECK, FLETCHER_STURM, 'informs', 2),
    edge(SALLY_BECK, WEST_TRADING_DESK, 'works_with', 4),
    edge(SALLY_BECK, ENRON_AMERICA, 'works_with', 6),
    edge(SALLY_BECK, AUGUST_REORG, 'informs', 1),
  ],
}

const JOHN_LAVORATO_SUBGRAPH: SubgraphResponse = {
  center_id: JOHN_LAVORATO,
  nodes: [
    node(JOHN_LAVORATO),
    node(SALLY_BECK),
    node(KENNETH_LAY),
    node(ENRON_AMERICA),
    node(FINANCE),
    node(GLOBAL_CROSSING_DEAL),
    node(APPROVE_GC_DEAL),
  ],
  edges: [
    edge(JOHN_LAVORATO, KENNETH_LAY, 'reports_to', 4),
    edge(SALLY_BECK, JOHN_LAVORATO, 'reports_to', 3),
    edge(JOHN_LAVORATO, ENRON_AMERICA, 'works_with', 5),
    edge(JOHN_LAVORATO, GLOBAL_CROSSING_DEAL, 'negotiating_with', 7),
    edge(JOHN_LAVORATO, FINANCE, 'requests_from', 2),
    edge(APPROVE_GC_DEAL, JOHN_LAVORATO, 'informs', 1),
  ],
}

const GLOBAL_CROSSING_DEAL_SUBGRAPH: SubgraphResponse = {
  center_id: GLOBAL_CROSSING_DEAL,
  nodes: [
    node(GLOBAL_CROSSING_DEAL),
    node(JOHN_LAVORATO),
    node(JOHN_ZUFFERLI),
    node(GLOBAL_CROSSING_LTD),
    node(ENRON_LEGAL),
    node(APPROVE_GC_DEAL),
  ],
  edges: [
    edge(JOHN_LAVORATO, GLOBAL_CROSSING_DEAL, 'negotiating_with', 7),
    edge(JOHN_ZUFFERLI, GLOBAL_CROSSING_LTD, 'negotiating_with', 6),
    edge(JOHN_ZUFFERLI, ENRON_LEGAL, 'informs', 2),
    edge(ENRON_LEGAL, GLOBAL_CROSSING_DEAL, 'requests_from', 3),
    edge(APPROVE_GC_DEAL, GLOBAL_CROSSING_DEAL, 'informs', 1),
  ],
}

const ENRON_AMERICA_SUBGRAPH: SubgraphResponse = {
  center_id: ENRON_AMERICA,
  nodes: [
    node(ENRON_AMERICA),
    node(SALLY_BECK),
    node(JOHN_LAVORATO),
    node(LOUISE_KITCHEN),
    node(FLETCHER_STURM),
    node(KENNETH_LAY),
    node(AUGUST_REORG),
  ],
  edges: [
    edge(SALLY_BECK, ENRON_AMERICA, 'works_with', 6),
    edge(JOHN_LAVORATO, ENRON_AMERICA, 'works_with', 5),
    edge(LOUISE_KITCHEN, ENRON_AMERICA, 'works_with', 4),
    edge(FLETCHER_STURM, ENRON_AMERICA, 'works_with', 3),
    edge(KENNETH_LAY, ENRON_AMERICA, 'works_with', 5),
    edge(AUGUST_REORG, ENRON_AMERICA, 'informs', 2),
  ],
}

const WEST_TRADING_DESK_SUBGRAPH: SubgraphResponse = {
  center_id: WEST_TRADING_DESK,
  nodes: [node(WEST_TRADING_DESK), node(SALLY_BECK), node(FLETCHER_STURM), node(ENRON_AMERICA)],
  edges: [
    edge(SALLY_BECK, WEST_TRADING_DESK, 'works_with', 4),
    edge(FLETCHER_STURM, WEST_TRADING_DESK, 'works_with', 3),
    edge(WEST_TRADING_DESK, ENRON_AMERICA, 'works_with', 2),
  ],
}

const LOUISE_KITCHEN_SUBGRAPH: SubgraphResponse = {
  center_id: LOUISE_KITCHEN,
  nodes: [node(LOUISE_KITCHEN), node(SALLY_BECK), node(ENRON_AMERICA), node(KENNETH_LAY)],
  edges: [
    edge(SALLY_BECK, LOUISE_KITCHEN, 'works_with', 5),
    edge(LOUISE_KITCHEN, ENRON_AMERICA, 'works_with', 4),
    edge(LOUISE_KITCHEN, KENNETH_LAY, 'reports_to', 2),
  ],
}

const FLETCHER_STURM_SUBGRAPH: SubgraphResponse = {
  center_id: FLETCHER_STURM,
  nodes: [node(FLETCHER_STURM), node(SALLY_BECK), node(ENRON_AMERICA), node(WEST_TRADING_DESK)],
  edges: [
    edge(SALLY_BECK, FLETCHER_STURM, 'informs', 2),
    edge(FLETCHER_STURM, ENRON_AMERICA, 'works_with', 3),
    edge(FLETCHER_STURM, WEST_TRADING_DESK, 'works_with', 3),
  ],
}

const KENNETH_LAY_SUBGRAPH: SubgraphResponse = {
  center_id: KENNETH_LAY,
  nodes: [node(KENNETH_LAY), node(JOHN_LAVORATO), node(ENRON_AMERICA), node(LOUISE_KITCHEN)],
  edges: [
    edge(JOHN_LAVORATO, KENNETH_LAY, 'reports_to', 4),
    edge(KENNETH_LAY, ENRON_AMERICA, 'works_with', 5),
    edge(LOUISE_KITCHEN, KENNETH_LAY, 'reports_to', 2),
  ],
}

const APPROVE_GC_DEAL_SUBGRAPH: SubgraphResponse = {
  center_id: APPROVE_GC_DEAL,
  nodes: [
    node(APPROVE_GC_DEAL),
    node(JOHN_LAVORATO),
    node(GLOBAL_CROSSING_DEAL),
    node(KENNETH_LAY),
  ],
  edges: [
    edge(APPROVE_GC_DEAL, JOHN_LAVORATO, 'informs', 1),
    edge(APPROVE_GC_DEAL, GLOBAL_CROSSING_DEAL, 'informs', 1),
    edge(KENNETH_LAY, APPROVE_GC_DEAL, 'informs', 2),
  ],
}

const AUGUST_REORG_SUBGRAPH: SubgraphResponse = {
  center_id: AUGUST_REORG,
  nodes: [node(AUGUST_REORG), node(SALLY_BECK), node(ENRON_AMERICA), node(JOHN_LAVORATO)],
  edges: [
    edge(SALLY_BECK, AUGUST_REORG, 'informs', 1),
    edge(AUGUST_REORG, ENRON_AMERICA, 'informs', 2),
    edge(AUGUST_REORG, JOHN_LAVORATO, 'informs', 2),
  ],
}

const FINANCE_SUBGRAPH: SubgraphResponse = {
  center_id: FINANCE,
  nodes: [node(FINANCE), node(JOHN_LAVORATO), node(SALLY_BECK), node(ENRON_AMERICA)],
  edges: [
    edge(JOHN_LAVORATO, FINANCE, 'requests_from', 2),
    edge(SALLY_BECK, FINANCE, 'requests_from', 3),
    edge(FINANCE, ENRON_AMERICA, 'informs', 2),
  ],
}

const ENRON_LEGAL_SUBGRAPH: SubgraphResponse = {
  center_id: ENRON_LEGAL,
  nodes: [node(ENRON_LEGAL), node(JOHN_ZUFFERLI), node(GLOBAL_CROSSING_DEAL), node(KENNETH_LAY)],
  edges: [
    edge(JOHN_ZUFFERLI, ENRON_LEGAL, 'informs', 2),
    edge(ENRON_LEGAL, GLOBAL_CROSSING_DEAL, 'requests_from', 3),
    edge(ENRON_LEGAL, KENNETH_LAY, 'informs', 2),
  ],
}

const GLOBAL_CROSSING_LTD_SUBGRAPH: SubgraphResponse = {
  center_id: GLOBAL_CROSSING_LTD,
  nodes: [
    node(GLOBAL_CROSSING_LTD),
    node(JOHN_ZUFFERLI),
    node(GLOBAL_CROSSING_DEAL),
    node(JOHN_LAVORATO),
  ],
  edges: [
    edge(JOHN_ZUFFERLI, GLOBAL_CROSSING_LTD, 'negotiating_with', 6),
    edge(JOHN_LAVORATO, GLOBAL_CROSSING_LTD, 'negotiating_with', 4),
    edge(GLOBAL_CROSSING_LTD, GLOBAL_CROSSING_DEAL, 'negotiating_with', 5),
  ],
}

const JOHN_ZUFFERLI_SUBGRAPH: SubgraphResponse = {
  center_id: JOHN_ZUFFERLI,
  nodes: [
    node(JOHN_ZUFFERLI),
    node(GLOBAL_CROSSING_LTD),
    node(ENRON_LEGAL),
    node(JOHN_LAVORATO),
  ],
  edges: [
    edge(JOHN_ZUFFERLI, GLOBAL_CROSSING_LTD, 'negotiating_with', 6),
    edge(JOHN_ZUFFERLI, ENRON_LEGAL, 'informs', 2),
    edge(JOHN_ZUFFERLI, JOHN_LAVORATO, 'reports_to', 3),
  ],
}

const MOCKS: Record<string, SubgraphResponse> = {
  [SALLY_BECK]: SALLY_BECK_SUBGRAPH,
  [JOHN_LAVORATO]: JOHN_LAVORATO_SUBGRAPH,
  [LOUISE_KITCHEN]: LOUISE_KITCHEN_SUBGRAPH,
  [FLETCHER_STURM]: FLETCHER_STURM_SUBGRAPH,
  [KENNETH_LAY]: KENNETH_LAY_SUBGRAPH,
  [JOHN_ZUFFERLI]: JOHN_ZUFFERLI_SUBGRAPH,
  [WEST_TRADING_DESK]: WEST_TRADING_DESK_SUBGRAPH,
  [ENRON_AMERICA]: ENRON_AMERICA_SUBGRAPH,
  [ENRON_LEGAL]: ENRON_LEGAL_SUBGRAPH,
  [FINANCE]: FINANCE_SUBGRAPH,
  [GLOBAL_CROSSING_LTD]: GLOBAL_CROSSING_LTD_SUBGRAPH,
  [GLOBAL_CROSSING_DEAL]: GLOBAL_CROSSING_DEAL_SUBGRAPH,
  [APPROVE_GC_DEAL]: APPROVE_GC_DEAL_SUBGRAPH,
  [AUGUST_REORG]: AUGUST_REORG_SUBGRAPH,
}

export const DEFAULT_CENTER_ID = SALLY_BECK

/**
 * Checks the identity invariants described at the top of this file. Returns a list of
 * problems (empty means healthy). Runs automatically in dev; also called by verification
 * scripts. This exists because the "one entity, one identity" rule was broken twice by
 * hand-maintained fixtures — an assertion is cheaper than noticing it in the UI.
 */
export function validateMockIntegrity(): string[] {
  const problems: string[] = []

  // 1. One name per ID, one ID per name.
  const nameToId = new Map<string, string>()
  for (const [id, def] of Object.entries(ENTITIES)) {
    const existing = nameToId.get(def.label)
    if (existing && existing !== id) {
      problems.push(`Name "${def.label}" is used by two different IDs: ${existing} and ${id}`)
    }
    nameToId.set(def.label, id)
  }

  for (const [centerId, subgraph] of Object.entries(MOCKS)) {
    const idsInFixture = new Set(subgraph.nodes.map((n) => n.id))

    // 2. A fixture's center must be one of its own nodes.
    if (!idsInFixture.has(centerId)) {
      problems.push(`Fixture ${centerId} does not contain its own center node`)
    }

    // 3. Node identity must match the canonical registry (guards against a hand-written
    //    node object sneaking past the node() helper).
    for (const n of subgraph.nodes) {
      const def = ENTITIES[n.id]
      if (!def) {
        problems.push(`Fixture ${centerId} references unregistered entity ${n.id}`)
        continue
      }
      if (n.label !== def.label) {
        problems.push(
          `Fixture ${centerId}: ${n.id} labelled "${n.label}" but canonical name is "${def.label}"`,
        )
      }
    }

    // 4. Every edge endpoint must be a node in the same fixture.
    for (const e of subgraph.edges) {
      if (!idsInFixture.has(e.source)) {
        problems.push(`Fixture ${centerId}: edge source ${e.source} is not a node in the fixture`)
      }
      if (!idsInFixture.has(e.target)) {
        problems.push(`Fixture ${centerId}: edge target ${e.target} is not a node in the fixture`)
      }
    }

    // 5. Every entity a user can see must itself be expandable to real data — this is the
    //    invariant whose absence caused the "— Contact A/B" placeholder bug.
    for (const n of subgraph.nodes) {
      if (!MOCKS[n.id]) {
        problems.push(
          `Entity ${n.id} appears in fixture ${centerId} but has no fixture of its own, ` +
            `so expanding it would return no neighbours`,
        )
      }
    }
  }

  return problems
}

if (import.meta.env?.DEV) {
  const problems = validateMockIntegrity()
  if (problems.length > 0) {
    console.error('graphMocks integrity check failed:\n' + problems.map((p) => `  - ${p}`).join('\n'))
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function labelFromId(id: string): string {
  const slug = id.split(':')[1] ?? id
  return slug
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function inferTypeFromId(id: string): string {
  const prefix = id.split(':')[0]
  if (prefix === 'org') return 'organization'
  return ['person', 'organization', 'deal', 'decision'].includes(prefix) ? prefix : 'person'
}

/**
 * Simulates GET /api/graph/{entity_id}/subgraph?depth={hops}. Returns a deep copy of the
 * matching fixture (so callers can't mutate shared mock data across calls).
 *
 * For an ID with no fixture — only reachable by typing/deep-linking an ID that isn't in the
 * mock universe, since invariant 5 above guarantees every *visible* node has one — this
 * returns the centre node alone with no edges. It deliberately does NOT invent neighbours:
 * an earlier version fabricated "{label} — Contact A/B" placeholder nodes here, which
 * rendered as duplicates of the entity being expanded. An empty neighbourhood is the honest
 * answer and matches what the real endpoint returns for an isolated node.
 */
export async function mockFetchSubgraph(
  entityId: string,
  hops: 1 | 2 = 1,
): Promise<SubgraphResponse> {
  void hops
  await delay(250 + Math.random() * 150)

  const fixture = MOCKS[entityId]
  if (fixture) {
    return structuredClone(fixture)
  }

  return {
    center_id: entityId,
    nodes: [
      {
        id: entityId,
        label: labelFromId(entityId),
        type: inferTypeFromId(entityId),
        mention_count: 0,
      },
    ],
    edges: [],
  }
}

// Directory of every entity known to the mock layer, for the search box. Built from the
// canonical registry rather than by walking fixtures, so search results carry exactly the
// same ID and name the graph does. On Day 41 this becomes a real call to
// GET /api/graph/search?q=... — kept as a separate function so swapping it out doesn't
// touch the graph canvas/merge logic.
const SEARCH_DIRECTORY: GraphSearchResult[] = Object.entries(ENTITIES).map(([id, def]) => ({
  id,
  name: def.label,
  type: def.type,
  mention_count: def.mention_count,
}))

/** Simulates GET /api/graph/search?q=... against the mock directory above. */
export async function mockSearchEntities(query: string): Promise<GraphSearchResult[]> {
  await delay(150 + Math.random() * 100)

  const q = query.trim().toLowerCase()
  if (!q) return []

  return SEARCH_DIRECTORY.filter((r) => r.name.toLowerCase().includes(q)).sort(
    (a, b) => b.mention_count - a.mention_count,
  )
}
