import { mockFetchSubgraph } from '@/mocks/graphMocks'
import type {
  ClaimResult,
  EntityClaimsResponse,
  EntityDetailResponse,
  EntityListItem,
  EntityListResponse,
  EntityTimelineResponse,
  TimelineEvent,
} from '@/types/entity'

// Mock data layer for the Entities pages (Day 39), matching the real EntityListResponse /
// EntityDetailResponse / EntityClaimsResponse / EntityTimelineResponse shapes from
// backend/src/api/models.py and backend/src/api/routes/entities.py — see src/types/entity.ts
// for the field-by-field mapping and the mock-only fields flagged there. Real integration
// happens on Day 41 (CLAUDE.md §9) — nothing here calls the live API.
//
// ---------------------------------------------------------------------------------------
// SINGLE SOURCE OF TRUTH (same rule graphMocks.ts had to learn the hard way on Day 38 —
// see that file's header comment and the Day 38 log's "mock data identity bug" section):
//
// Every entity has exactly ONE canonical id/name/type, declared once in ENTITIES below.
// Every claim is declared ONCE in CLAIMS, as an edge between two ENTITIES ids — never
// authored separately per-entity. Both mockFetchEntityClaims and mockFetchEntityTimeline
// derive their per-entity view by *filtering* CLAIMS (subject_id or object_id matches),
// exactly like the real Cypher query (`WHERE c.subject_id = $entity_id OR c.object_id =
// $entity_id`). This is deliberate: a claim is one fact shared by two entities, so if it
// were hand-duplicated into two entities' claim lists, an edit to one copy could silently
// drift from the other. Filtering a single array makes that class of bug structurally
// impossible instead of relying on careful editing.
// ---------------------------------------------------------------------------------------

// ---- Canonical entity IDs (type:slug:email-slug, per CLAUDE.md §8.1) ----
//
// The first 14 IDs below are copied verbatim from src/mocks/graphMocks.ts's own canonical
// registry (that file doesn't export its constants, and it's a Day 38 file this session
// must not modify — see the Day 39 brief's scope boundaries — so the strings are
// duplicated here rather than imported). Keeping the same id/name pair for these 14 means
// the Graph Explorer's double-click navigation, and this page's own Relationships tab
// (which calls graphMocks' mockFetchSubgraph directly), land on the exact same entity
// identity as everywhere else in the app. If graphMocks.ts's registry ever changes, these
// must be updated to match — validateEntityMockIntegrity() below cannot catch drift
// against a file it doesn't import, so a future editor changing one file must remember
// the other exists.
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

// These 6 are new — not present in graphMocks.ts. They exist purely so the entity list has
// enough rows to exercise pagination/search, and to exercise the "entity has zero claims"
// empty state on the detail page's Claims/Timeline tabs. Because they have no fixture in
// graphMocks.ts, their Relationships tab will honestly show "no known relationships"
// (graphMocks' mockFetchSubgraph fallback for an unmapped id) rather than fabricated data.
const JEFFREY_MCMAHON = 'person:mcmahon-jeffrey:jeffrey-mcmahon-at-enron-com'
const GREG_WHALLEY = 'person:whalley-greg:greg-whalley-at-enron-com'
const ARTHUR_ANDERSEN = 'org:arthur-andersen:arthur-andersen'
const ENRON_BROADBAND = 'org:enron-broadband-services:enron-broadband-services'
const EOTT_RESTRUCTURING = 'deal:eott-energy-restructuring:eott-energy-restructuring'
const FREEZE_401K = 'decision:freeze-401k-trading-window:freeze-401k-trading-window'

interface EntityDef {
  name: string
  type: string
  mention_count: number
  aliases: string[]
  first_seen: string
  last_seen: string
  org_type: string | null
}

// The 4 "detailed" profiles the Day 39 brief asks for (one of each entity type, all
// carrying real claim data below) are Sally Beck, Enron America, the Global Crossing deal,
// and the August 2001 Reorganization decision — chosen because they already anchor
// graphMocks.ts's richest fixtures, so this page's data reads as the same world as the
// Graph Explorer rather than a disconnected mock universe.
const ENTITIES: Record<string, EntityDef> = {
  [SALLY_BECK]: {
    name: 'Sally Beck',
    type: 'person',
    mention_count: 42,
    aliases: ['S. Beck', 'Sally'],
    first_seen: '2000-11-01',
    last_seen: '2001-12-02',
    org_type: null,
  },
  [JOHN_LAVORATO]: {
    name: 'John Lavorato',
    type: 'person',
    mention_count: 28,
    aliases: ['J. Lavorato'],
    first_seen: '2000-09-01',
    last_seen: '2001-11-20',
    org_type: null,
  },
  [LOUISE_KITCHEN]: {
    name: 'Louise Kitchen',
    type: 'person',
    mention_count: 35,
    aliases: ['L. Kitchen'],
    first_seen: '2000-06-01',
    last_seen: '2001-12-10',
    org_type: null,
  },
  [FLETCHER_STURM]: {
    name: 'Fletcher Sturm',
    type: 'person',
    mention_count: 12,
    aliases: [],
    first_seen: '2001-02-01',
    last_seen: '2001-09-15',
    org_type: null,
  },
  [KENNETH_LAY]: {
    name: 'Kenneth Lay',
    type: 'person',
    mention_count: 82,
    aliases: ['Ken Lay', 'K. Lay'],
    first_seen: '1999-01-01',
    last_seen: '2001-12-20',
    org_type: null,
  },
  [JOHN_ZUFFERLI]: {
    name: 'John Zufferli',
    type: 'person',
    mention_count: 19,
    aliases: ['J. Zufferli'],
    first_seen: '2001-04-01',
    last_seen: '2001-08-10',
    org_type: null,
  },
  [WEST_TRADING_DESK]: {
    name: 'West Trading Desk',
    type: 'organization',
    mention_count: 8,
    aliases: [],
    first_seen: '2001-01-15',
    last_seen: '2001-09-01',
    org_type: 'business_unit',
  },
  [ENRON_AMERICA]: {
    name: 'Enron America',
    type: 'organization',
    mention_count: 78,
    aliases: ['Enron North America', 'ENA'],
    first_seen: '1999-01-01',
    last_seen: '2001-12-15',
    org_type: 'business_unit',
  },
  [ENRON_LEGAL]: {
    name: 'Enron Legal',
    type: 'organization',
    mention_count: 22,
    aliases: ['Legal Dept'],
    first_seen: '2000-03-01',
    last_seen: '2001-08-30',
    org_type: 'internal_department',
  },
  [FINANCE]: {
    name: 'Finance',
    type: 'organization',
    mention_count: 9,
    aliases: [],
    first_seen: '2000-05-01',
    last_seen: '2001-07-01',
    org_type: 'internal_department',
  },
  [GLOBAL_CROSSING_LTD]: {
    name: 'Global Crossing Ltd',
    type: 'organization',
    mention_count: 45,
    aliases: ['Global Crossing'],
    first_seen: '2001-04-01',
    last_seen: '2001-08-15',
    org_type: 'external_company',
  },
  [GLOBAL_CROSSING_DEAL]: {
    name: 'Global Crossing Transaction',
    type: 'deal',
    mention_count: 15,
    aliases: [],
    first_seen: '2001-05-01',
    last_seen: '2001-08-01',
    org_type: null,
  },
  [APPROVE_GC_DEAL]: {
    name: 'Approve Global Crossing Deal',
    type: 'decision',
    mention_count: 6,
    aliases: [],
    first_seen: '2001-08-01',
    last_seen: '2001-08-05',
    org_type: null,
  },
  [AUGUST_REORG]: {
    name: 'August 2001 Reorganization',
    type: 'decision',
    mention_count: 55,
    aliases: [],
    first_seen: '2001-07-01',
    last_seen: '2001-08-25',
    org_type: null,
  },
  [JEFFREY_MCMAHON]: {
    name: 'Jeffrey McMahon',
    type: 'person',
    mention_count: 24,
    aliases: ['J. McMahon'],
    first_seen: '2000-08-01',
    last_seen: '2001-10-01',
    org_type: null,
  },
  [GREG_WHALLEY]: {
    name: 'Greg Whalley',
    type: 'person',
    mention_count: 31,
    aliases: ['G. Whalley'],
    first_seen: '2000-10-01',
    last_seen: '2001-11-01',
    org_type: null,
  },
  [ARTHUR_ANDERSEN]: {
    name: 'Arthur Andersen',
    type: 'organization',
    mention_count: 17,
    aliases: ['Andersen'],
    first_seen: '2000-01-01',
    last_seen: '2001-11-01',
    org_type: 'external_company',
  },
  [ENRON_BROADBAND]: {
    name: 'Enron Broadband Services',
    type: 'organization',
    mention_count: 26,
    aliases: ['EBS'],
    first_seen: '2000-02-01',
    last_seen: '2001-06-01',
    org_type: 'business_unit',
  },
  [EOTT_RESTRUCTURING]: {
    name: 'EOTT Energy Restructuring',
    type: 'deal',
    mention_count: 11,
    aliases: [],
    first_seen: '2001-02-01',
    last_seen: '2001-06-01',
    org_type: null,
  },
  [FREEZE_401K]: {
    name: 'Freeze 401(k) Trading Window',
    type: 'decision',
    mention_count: 14,
    aliases: [],
    first_seen: '2001-10-01',
    last_seen: '2001-10-26',
    org_type: null,
  },
}

// ---- Claims — the single canonical fact table, see header comment ----

interface ClaimOpts {
  confidence: number
  validFrom: string
  validTo?: string | null
  status: string
  evidenceIds?: string[]
  mentionCount?: number
}

function entityName(id: string): string {
  const def = ENTITIES[id]
  if (!def) {
    throw new Error(`entityMocks: no canonical entity registered for id "${id}"`)
  }
  return def.name
}

/**
 * Builds a ClaimResult, looking up subject_name/object_name from the ENTITIES registry
 * rather than accepting them as literals — this is what makes it structurally impossible
 * for a claim to cite a name that doesn't match its subject/object id.
 */
function claim(claim_id: string, subjectId: string, claim_type: string, objectId: string, opts: ClaimOpts): ClaimResult {
  return {
    claim_id,
    claim_type,
    subject_id: subjectId,
    subject_name: entityName(subjectId),
    object_id: objectId,
    object_name: entityName(objectId),
    confidence: opts.confidence,
    valid_from: opts.validFrom,
    valid_to: opts.validTo ?? null,
    status: opts.status,
    mention_count: opts.mentionCount ?? 0,
    evidence_ids: opts.evidenceIds ?? [],
  }
}

const CLAIMS: ClaimResult[] = [
  // Sally Beck (7 claims — reports_to, works_with x2, informs x2, one superseded, one review)
  claim('claim_001', SALLY_BECK, 'reports_to', JOHN_LAVORATO, {
    confidence: 0.88,
    validFrom: '2001-08-01',
    status: 'active',
    evidenceIds: ['evidence_2210', 'evidence_2211'],
    mentionCount: 2,
  }),
  claim('claim_002', SALLY_BECK, 'works_with', LOUISE_KITCHEN, {
    confidence: 0.75,
    validFrom: '2001-03-15',
    status: 'active',
    evidenceIds: ['evidence_1840'],
    mentionCount: 1,
  }),
  claim('claim_003', SALLY_BECK, 'informs', FLETCHER_STURM, {
    confidence: 0.62,
    validFrom: '2001-05-10',
    status: 'active',
    evidenceIds: ['evidence_1955'],
    mentionCount: 1,
  }),
  claim('claim_004', SALLY_BECK, 'works_with', WEST_TRADING_DESK, {
    confidence: 0.81,
    validFrom: '2001-02-01',
    status: 'active',
    evidenceIds: ['evidence_1622', 'evidence_1623'],
    mentionCount: 2,
  }),
  claim('claim_005', SALLY_BECK, 'works_with', ENRON_AMERICA, {
    confidence: 0.91,
    validFrom: '2000-11-01',
    status: 'active',
    evidenceIds: ['evidence_1401', 'evidence_1402', 'evidence_1403'],
    mentionCount: 3,
  }),
  claim('claim_006', SALLY_BECK, 'informs', AUGUST_REORG, {
    confidence: 0.55,
    validFrom: '2001-08-15',
    status: 'review',
    // deliberately empty — exercises the "no evidence yet" state on the Claims tab
  }),
  claim('claim_007', SALLY_BECK, 'reports_to', KENNETH_LAY, {
    confidence: 0.45,
    validFrom: '2000-01-01',
    validTo: '2001-07-31',
    status: 'superseded',
    evidenceIds: ['evidence_0980'],
    mentionCount: 1,
  }),

  // Enron America (7 claims — mostly works_with as the object, plus informs/requests_from)
  claim('claim_008', JOHN_LAVORATO, 'works_with', ENRON_AMERICA, {
    confidence: 0.79,
    validFrom: '2000-09-01',
    status: 'active',
    evidenceIds: ['evidence_1105'],
    mentionCount: 1,
  }),
  claim('claim_009', LOUISE_KITCHEN, 'works_with', ENRON_AMERICA, {
    confidence: 0.7,
    validFrom: '2001-01-10',
    status: 'active',
    evidenceIds: ['evidence_1290'],
    mentionCount: 1,
  }),
  claim('claim_010', FLETCHER_STURM, 'works_with', ENRON_AMERICA, {
    confidence: 0.58,
    validFrom: '2001-04-01',
    status: 'active',
    evidenceIds: ['evidence_1710'],
    mentionCount: 1,
  }),
  claim('claim_011', KENNETH_LAY, 'works_with', ENRON_AMERICA, {
    confidence: 0.93,
    validFrom: '1999-01-01',
    status: 'active',
    evidenceIds: ['evidence_0102', 'evidence_0103'],
    mentionCount: 2,
  }),
  claim('claim_012', AUGUST_REORG, 'informs', ENRON_AMERICA, {
    confidence: 0.66,
    validFrom: '2001-08-20',
    status: 'active',
    evidenceIds: ['evidence_2290'],
    mentionCount: 1,
  }),
  claim('claim_013', ENRON_AMERICA, 'requests_from', FINANCE, {
    confidence: 0.5,
    validFrom: '2001-06-01',
    status: 'review',
  }),

  // Global Crossing Transaction (5 claims — negotiating_with x3, requests_from, informs)
  claim('claim_014', JOHN_LAVORATO, 'negotiating_with', GLOBAL_CROSSING_DEAL, {
    confidence: 0.84,
    validFrom: '2001-07-01',
    status: 'active',
    evidenceIds: ['evidence_1980', 'evidence_1981'],
    mentionCount: 2,
  }),
  claim('claim_015', ENRON_LEGAL, 'requests_from', GLOBAL_CROSSING_DEAL, {
    confidence: 0.68,
    validFrom: '2001-07-15',
    status: 'active',
    evidenceIds: ['evidence_2005', 'evidence_2006', 'evidence_2007'],
    mentionCount: 3,
  }),
  claim('claim_016', APPROVE_GC_DEAL, 'informs', GLOBAL_CROSSING_DEAL, {
    confidence: 0.6,
    validFrom: '2001-08-01',
    status: 'active',
    evidenceIds: ['evidence_2150'],
    mentionCount: 1,
  }),
  claim('claim_017', GLOBAL_CROSSING_LTD, 'negotiating_with', GLOBAL_CROSSING_DEAL, {
    confidence: 0.72,
    validFrom: '2001-05-01',
    validTo: '2001-07-01',
    status: 'superseded',
    evidenceIds: ['evidence_1750'],
    mentionCount: 1,
  }),
  claim('claim_018', JOHN_ZUFFERLI, 'negotiating_with', GLOBAL_CROSSING_DEAL, {
    confidence: 0.4,
    validFrom: '2001-06-10',
    status: 'review',
  }),

  // August 2001 Reorganization (6 claims, including claim_006/claim_012 above — all informs)
  claim('claim_019', AUGUST_REORG, 'informs', JOHN_LAVORATO, {
    confidence: 0.63,
    validFrom: '2001-08-25',
    status: 'active',
    evidenceIds: ['evidence_2305'],
    mentionCount: 1,
  }),
  claim('claim_020', AUGUST_REORG, 'informs', KENNETH_LAY, {
    confidence: 0.71,
    validFrom: '2001-08-10',
    status: 'active',
    evidenceIds: ['evidence_2260', 'evidence_2261'],
    mentionCount: 2,
  }),
  claim('claim_021', AUGUST_REORG, 'informs', LOUISE_KITCHEN, {
    confidence: 0.49,
    validFrom: '2001-08-18',
    status: 'review',
  }),
  claim('claim_022', GREG_WHALLEY, 'informs', AUGUST_REORG, {
    confidence: 0.58,
    validFrom: '2001-07-01',
    validTo: '2001-08-01',
    status: 'superseded',
    evidenceIds: ['evidence_2010'],
    mentionCount: 1,
  }),
]

// Human-readable verb per claim type, for the timeline's description text. Keys must cover
// exactly the 5-type closed vocabulary from CLAUDE.md §8.6.
const CLAIM_VERB: Record<string, string> = {
  reports_to: 'reports to',
  works_with: 'works with',
  negotiating_with: 'is negotiating with',
  requests_from: 'requests input from',
  informs: 'informs',
}

function describeClaim(c: ClaimResult): string {
  const verb = CLAIM_VERB[c.claim_type] ?? c.claim_type
  return `${c.subject_name} ${verb} ${c.object_name}`
}

// ---- Integrity check — same pattern as graphMocks.ts's validateMockIntegrity() ----

export function validateEntityMockIntegrity(): string[] {
  const problems: string[] = []
  const validClaimTypes = new Set(Object.keys(CLAIM_VERB))

  const nameToId = new Map<string, string>()
  for (const [id, def] of Object.entries(ENTITIES)) {
    const existing = nameToId.get(def.name)
    if (existing && existing !== id) {
      problems.push(`Name "${def.name}" is used by two different entity ids: ${existing} and ${id}`)
    }
    nameToId.set(def.name, id)
  }

  const seenClaimIds = new Set<string>()
  for (const c of CLAIMS) {
    if (seenClaimIds.has(c.claim_id)) {
      problems.push(`Duplicate claim_id: ${c.claim_id}`)
    }
    seenClaimIds.add(c.claim_id)

    if (!validClaimTypes.has(c.claim_type)) {
      problems.push(`Claim ${c.claim_id} has claim_type "${c.claim_type}", outside the 5-type vocabulary`)
    }
    if (!ENTITIES[c.subject_id]) {
      problems.push(`Claim ${c.claim_id} references unregistered subject_id ${c.subject_id}`)
    } else if (c.subject_name !== ENTITIES[c.subject_id].name) {
      problems.push(`Claim ${c.claim_id}: subject_name "${c.subject_name}" doesn't match registry name for ${c.subject_id}`)
    }
    if (!ENTITIES[c.object_id]) {
      problems.push(`Claim ${c.claim_id} references unregistered object_id ${c.object_id}`)
    } else if (c.object_name !== ENTITIES[c.object_id].name) {
      problems.push(`Claim ${c.claim_id}: object_name "${c.object_name}" doesn't match registry name for ${c.object_id}`)
    }
    if (c.confidence < 0 || c.confidence > 1) {
      problems.push(`Claim ${c.claim_id} has out-of-range confidence ${c.confidence}`)
    }
  }

  return problems
}

if (import.meta.env?.DEV) {
  const problems = validateEntityMockIntegrity()
  if (problems.length > 0) {
    console.error('entityMocks integrity check failed:\n' + problems.map((p) => `  - ${p}`).join('\n'))
  }
}

// ---- Cross-file consistency check against graphMocks.ts ----
//
// The Claims tab (this file) and the Relationships tab (graphMocks.ts, via
// mockFetchSubgraph) each show a "how many sources back this relationship" number for the
// same underlying fact whenever a claim's (subject, claim_type, object) triple also
// appears as a graph edge. These numbers were originally authored independently — one
// file's evidence_ids arrays, the other file's hand-picked edge-thickness numbers — and a
// real instance of them silently drifting apart was found and fixed on Day 39 (Kenneth
// Lay ↔ Enron America: 2 sources on the Claims tab, 5 on the Relationships tab, for what
// should have been the exact same claim). This check re-derives every edge that graphMocks
// draws for an entity appearing in CLAIMS and flags any triple present in both files whose
// counts disagree, so a future edit to either file's numbers that reintroduces that drift
// fails loudly here instead of being noticed later by a user comparing two tabs. It only
// calls graphMocks.ts's public mockFetchSubgraph — it doesn't reach into that file's
// internals, so it can't verify the 14 duplicated id strings themselves stay in sync (see
// the header comment above), only that whatever graphMocks currently returns agrees with
// CLAIMS wherever both describe the same relationship.
export async function validateGraphClaimConsistency(): Promise<string[]> {
  const problems: string[] = []

  const centerIds = new Set<string>()
  for (const c of CLAIMS) {
    centerIds.add(c.subject_id)
    centerIds.add(c.object_id)
  }

  // A given edge (e.g. Kenneth Lay -> Enron America) is drawn by more than one fixture —
  // once as an outgoing edge from Kenneth Lay's own subgraph, again as an incoming edge on
  // Enron America's. Recording every observed value per key (not just the last one written)
  // is what lets this catch the two fixtures disagreeing with *each other*, not only the
  // last-fetched one disagreeing with entityMocks — a plain last-write-wins Map missed
  // exactly this during verification: reintroducing the original Kenneth Lay/Enron America
  // bug in only one of its two fixture copies still matched entityMocks by coincidence,
  // because whichever fixture happened to be fetched last still held the correct value.
  const edgeCounts = new Map<string, Set<number>>()
  for (const id of centerIds) {
    const subgraph = await mockFetchSubgraph(id, 1)
    for (const e of subgraph.edges) {
      const key = `${e.source}|${e.type}|${e.target}`
      const values = edgeCounts.get(key) ?? new Set<number>()
      values.add(e.claim_count ?? 0)
      edgeCounts.set(key, values)
    }
  }

  for (const [key, values] of edgeCounts) {
    if (values.size > 1) {
      problems.push(`graphMocks internal inconsistency: edge "${key}" has different claim_count values across the fixtures that draw it: ${[...values].join(', ')}`)
    }
  }

  for (const c of CLAIMS) {
    const key = `${c.subject_id}|${c.claim_type}|${c.object_id}`
    const values = edgeCounts.get(key)
    if (values && !values.has(c.evidence_ids.length)) {
      problems.push(
        `Claim ${c.claim_id} (${c.subject_name} ${c.claim_type} ${c.object_name}): ` +
          `entityMocks has ${c.evidence_ids.length} evidence_ids but graphMocks' matching ` +
          `edge reports claim_count ${[...values].join(' / ')}`,
      )
    }
  }

  return problems
}

if (import.meta.env?.DEV) {
  validateGraphClaimConsistency().then((problems) => {
    if (problems.length > 0) {
      console.error(
        'entityMocks/graphMocks cross-file consistency check failed:\n' +
          problems.map((p) => `  - ${p}`).join('\n'),
      )
    }
  })
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function claimCountFor(entityId: string): number {
  return CLAIMS.filter((c) => c.subject_id === entityId || c.object_id === entityId).length
}

function toListItem(id: string, def: EntityDef): EntityListItem {
  return {
    id,
    name: def.name,
    type: def.type,
    mention_count: def.mention_count,
    claim_count: claimCountFor(id),
  }
}

/** Simulates GET /api/entities?type=&search=&skip=&limit= (backend/src/api/routes/entities.py). */
export async function mockFetchEntities(opts: {
  type?: string
  search?: string
  skip?: number
  limit?: number
} = {}): Promise<EntityListResponse> {
  await delay(200 + Math.random() * 200)

  const skip = opts.skip ?? 0
  const limit = opts.limit ?? 10

  let items = Object.entries(ENTITIES).map(([id, def]) => toListItem(id, def))

  if (opts.type) {
    items = items.filter((e) => e.type === opts.type)
  }
  if (opts.search?.trim()) {
    const q = opts.search.trim().toLowerCase()
    items = items.filter((e) => e.name.toLowerCase().includes(q))
  }

  items.sort((a, b) => b.mention_count - a.mention_count)

  const total = items.length
  const page = items.slice(skip, skip + limit)

  return { entities: page, total, skip, limit }
}

/** Simulates GET /api/entities/{id} (backend/src/api/routes/entities.py). */
export async function mockFetchEntityDetail(id: string): Promise<EntityDetailResponse> {
  await delay(200 + Math.random() * 150)

  const def = ENTITIES[id]
  if (!def) {
    throw new Error(`Entity '${id}' not found`)
  }

  return {
    id,
    name: def.name,
    type: def.type,
    mention_count: def.mention_count,
    aliases: def.aliases,
    emails: [],
    org_type: def.org_type,
    first_seen: def.first_seen,
    last_seen: def.last_seen,
    claim_count: claimCountFor(id),
  }
}

/** Simulates GET /api/entities/{id}/claims?claim_type=&status= (backend/src/api/routes/entities.py). */
export async function mockFetchEntityClaims(
  id: string,
  claimType?: string,
  status?: string,
): Promise<EntityClaimsResponse> {
  await delay(150 + Math.random() * 150)

  let claims = CLAIMS.filter((c) => c.subject_id === id || c.object_id === id)
  if (claimType) {
    claims = claims.filter((c) => c.claim_type === claimType)
  }
  if (status) {
    claims = claims.filter((c) => c.status === status)
  }
  claims = [...claims].sort((a, b) => b.confidence - a.confidence)

  return { entity_id: id, claims, total: claims.length }
}

/** Simulates GET /api/entities/{id}/timeline (backend/src/api/routes/entities.py). */
export async function mockFetchEntityTimeline(id: string): Promise<EntityTimelineResponse> {
  await delay(150 + Math.random() * 150)

  const def = ENTITIES[id]
  const claims = CLAIMS.filter((c) => c.subject_id === id || c.object_id === id).sort((a, b) =>
    (a.valid_from ?? '').localeCompare(b.valid_from ?? ''),
  )

  const events: TimelineEvent[] = claims.map((c) => ({
    claim_id: c.claim_id,
    claim_type: c.claim_type,
    subject_name: c.subject_name,
    object_name: c.object_name,
    description: describeClaim(c),
    valid_from: c.valid_from,
    valid_to: c.valid_to,
    status: c.status,
    confidence: c.confidence,
  }))

  return { entity_id: id, entity_name: def?.name ?? '', events }
}
