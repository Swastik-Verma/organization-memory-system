// The 8 relationship types the graph explorer renders, and their directionality.
//
// They come from two different places in the backend, which is why this vocabulary is
// broader than the 5-claim-type closed vocabulary in claimTypes.ts:
//
//   • 5 CLAIM types  — the `claim_type` property on Claim nodes, surfaced through
//     GET /api/entities/{id}/claims and collapsed into direct entity-to-entity edges by
//     src/lib/graphData.ts.
//   • 3 STRUCTURAL types — real Neo4j relationship types (PARTY, MADE_BY, AFFECTS)
//     connecting a Person/Organization to a Deal or Decision, surfaced through
//     GET /api/graph/{id}/subgraph and lowercased by graphData.ts.
//
// Directionality decides whether the canvas draws an arrowhead. A symmetric relationship
// drawn with an arrow would assert something the data doesn't say ("A works_with B" and
// "B works_with A" are the same fact), so those two render as plain lines.

export const SYMMETRIC_RELATIONSHIP_TYPES = new Set(['works_with', 'negotiating_with'])

export const ASYMMETRIC_RELATIONSHIP_TYPES = new Set([
  'reports_to',
  'requests_from',
  'informs',
  'made_by',
  'affects',
  'party',
])

/** Structural Neo4j relationship types worth showing, mapped to their display form.
 *  Everything else the raw subgraph returns (SUBJECT, OBJECT, SENT_BY, SENT_TO,
 *  FROM_MESSAGE, SUPPORTED_BY, SUPERSEDES, CONFLICTS_WITH) is either an internal plumbing
 *  edge or a Message edge, and is dropped — see graphData.ts. */
export const STRUCTURAL_RELATIONSHIP_TYPES: Record<string, string> = {
  PARTY: 'party',
  MADE_BY: 'made_by',
  AFFECTS: 'affects',
}

export function isSymmetricRelationship(type: string): boolean {
  return SYMMETRIC_RELATIONSHIP_TYPES.has(type)
}

export const RELATIONSHIP_TYPE_LABELS: Record<string, string> = {
  reports_to: 'Reports To',
  works_with: 'Works With',
  negotiating_with: 'Negotiating With',
  requests_from: 'Requests From',
  informs: 'Informs',
  party: 'Party To',
  made_by: 'Made By',
  affects: 'Affects',
}

export function relationshipTypeLabel(type: string): string {
  return RELATIONSHIP_TYPE_LABELS[type] ?? type
}
