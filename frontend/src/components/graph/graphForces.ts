import type { GraphNode } from '@/types/graph'

// Force-simulation tuning and the label geometry it depends on, kept in its own module so
// the headless layout test can exercise the exact same code the canvas uses rather than a
// copy of it that can drift.
//
// The key thing to understand here: the simulation works in GRAPH coordinates, but node
// labels are drawn at a fixed SCREEN size (the canvas renderer divides the font size by
// globalScale so text stays legible at any zoom). So a label's footprint in graph units is
// `widthInPixels / scale` — it grows as you zoom out. Any spacing rule that ignores this
// will look fine at one zoom level and overlap badly at another.

export const NODE_LABEL_FONT_PX = 12
export const EDGE_LABEL_FONT_PX = 10

// force-graph auto-sets zoom to ZOOM2NODES_FACTOR / cbrt(nodeCount) whenever graph data
// changes and the user hasn't manually zoomed (see force-graph's onFinishUpdate handler).
// Mirrored here so spacing can be expressed in screen pixels and converted to graph units.
const ZOOM2NODES_FACTOR = 4

export function defaultZoomForNodeCount(nodeCount: number): number {
  return ZOOM2NODES_FACTOR / Math.cbrt(Math.max(nodeCount, 1))
}

export function nodeRadius(mentionCount: number): number {
  // sqrt scale so an 80-mention node isn't 16x a 5-mention one — clamped to keep the
  // smallest nodes visible (~4-6px) and the largest prominent but not overwhelming (~16-20px).
  return Math.max(4, Math.min(20, 3 + Math.sqrt(Math.max(mentionCount, 0)) * 1.6))
}

export function truncateLabel(label: string, max = 15): string {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label
}

// Canvas measureText isn't available where the layout test runs (no canvas in this
// environment), and the simulation needs a width before the first paint anyway. 0.55em per
// character is a good average for a sans-serif stack at these sizes.
const AVG_CHAR_WIDTH_EM = 0.55

export function estimateTextWidthPx(text: string, fontPx: number): number {
  return text.length * fontPx * AVG_CHAR_WIDTH_EM
}

export function nodeLabelWidthPx(node: GraphNode): number {
  return estimateTextWidthPx(truncateLabel(node.label), NODE_LABEL_FONT_PX)
}

// Repulsion between all node pairs. The user-facing symptom of too little of this is
// labels landing on top of neighbouring nodes.
export const CHARGE_STRENGTH = -400

// Target on-screen separation between two linked nodes, in pixels, at the default zoom.
const LINK_DISTANCE_PX = 260

// Extra breathing room around each node's collision envelope, in screen pixels.
const COLLISION_PADDING_PX = 16

export function linkDistanceForScale(scale: number): number {
  return LINK_DISTANCE_PX / scale
}

/**
 * The radius (in GRAPH units) that must stay clear around a node so that neither its circle
 * nor its label can be overlapped by a neighbour. Takes the larger of the circle radius and
 * half the label width, because for a small node with a long name the label — not the
 * circle — is what actually collides.
 */
export function nodeClearRadius(node: GraphNode, scale: number): number {
  const circle = nodeRadius(node.mention_count)
  const labelHalfWidth = nodeLabelWidthPx(node) / 2 / scale
  return Math.max(circle, labelHalfWidth) + COLLISION_PADDING_PX / scale
}

type SimNode = GraphNode & { x?: number; y?: number; vx?: number; vy?: number }

/**
 * A collision force in the shape d3-force expects, written by hand rather than pulled from
 * d3-force-3d. force-graph depends on d3-force-3d internally, but it is not a declared
 * dependency of this app, and importing a transitive dependency directly is the kind of
 * thing that breaks on a future install. This is ~20 lines, needs a custom label-aware
 * radius anyway, and runs on at most a few dozen nodes.
 *
 * Nudges velocities apart (rather than teleporting positions) so it composes with the other
 * forces the way d3's own forceCollide does. `getScale` is read on every tick because the
 * zoom level changes as nodes are added.
 */
export function createCollisionForce(
  getScale: () => number,
  iterations = 2,
): ((alpha: number) => void) & { initialize?: (nodes: SimNode[]) => void } {
  let nodes: SimNode[] = []

  const force = () => {
    const scale = getScale()
    const radii = nodes.map((n) => nodeClearRadius(n, scale))

    for (let iter = 0; iter < iterations; iter++) {
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i]
        if (a.x == null || a.y == null) continue
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j]
          if (b.x == null || b.y == null) continue

          const minDistance = radii[i] + radii[j]
          let dx = b.x + (b.vx ?? 0) - (a.x + (a.vx ?? 0))
          let dy = b.y + (b.vy ?? 0) - (a.y + (a.vy ?? 0))
          let distance = Math.sqrt(dx * dx + dy * dy)

          if (distance >= minDistance) continue

          // Perfectly coincident nodes have no direction to separate along; nudge them.
          if (distance === 0) {
            dx = (i % 2 === 0 ? 1 : -1) * 0.5
            dy = (j % 2 === 0 ? 1 : -1) * 0.5
            distance = Math.sqrt(dx * dx + dy * dy)
          }

          const push = ((minDistance - distance) / distance) * 0.5
          const pushX = dx * push
          const pushY = dy * push

          a.vx = (a.vx ?? 0) - pushX
          a.vy = (a.vy ?? 0) - pushY
          b.vx = (b.vx ?? 0) + pushX
          b.vy = (b.vy ?? 0) + pushY
        }
      }
    }
  }

  force.initialize = (ns: SimNode[]) => {
    nodes = ns
  }

  return force
}


// ---------------------------------------------------------------------------------------
// Parallel-edge curvature (Day 41)
// ---------------------------------------------------------------------------------------
//
// Two entities routinely hold several different relationships at once. Sally Beck and Brent
// Price are connected by six separate real claims — works_with, informs in both directions,
// requests_from, and reports_to in BOTH directions (a genuine contradiction in the extracted
// data). Drawn as straight lines all six land exactly on top of each other: one thick line
// with six relationship labels stacked at an identical midpoint. Curving them fans the
// bundle out into distinguishable arcs.
//
// Lives here rather than in GraphCanvas.tsx for the same reason the force tuning does — this
// module is importable without a DOM or a canvas context, so the real function can be
// exercised by a test instead of a copy of it.

export const MAX_CURVATURE = 0.45

/** Stable identity for a link, tolerant of force-graph having already replaced the string
 *  endpoints with node objects once the simulation is running. */
export function linkId(
  source: { id: string } | string,
  target: { id: string } | string,
  type: string,
): string {
  const s = typeof source === 'string' ? source : source.id
  const t = typeof target === 'string' ? target : target.id
  return `${s}::${type}::${t}`
}

/**
 * Assigns each edge a curvature so parallel edges between the same pair of nodes bow away
 * from each other instead of overlapping.
 *
 * Edges are grouped by UNORDERED pair, so an A->B and a B->A edge belong to the same bundle
 * and get different arcs rather than two arcs bowing into each other. A pair with a single
 * edge stays perfectly straight (curvature 0), so the common case is unaffected.
 */
export function computeCurvatures(
  edges: Array<{ source: string; target: string; type: string }>,
): Map<string, number> {
  const byPair = new Map<string, Array<{ source: string; target: string; type: string }>>()
  for (const edge of edges) {
    const pair = [edge.source, edge.target].sort().join('|')
    const bundle = byPair.get(pair)
    if (bundle) bundle.push(edge)
    else byPair.set(pair, [edge])
  }

  const curvatures = new Map<string, number>()
  for (const bundle of byPair.values()) {
    // Sorted so an edge's arc doesn't reshuffle when a merge changes the array's order.
    bundle.sort((a, b) =>
      linkId(a.source, a.target, a.type).localeCompare(linkId(b.source, b.target, b.type)),
    )
    const n = bundle.length
    bundle.forEach((edge, i) => {
      const curvature = n === 1 ? 0 : -MAX_CURVATURE + (2 * MAX_CURVATURE * i) / (n - 1)
      curvatures.set(linkId(edge.source, edge.target, edge.type), curvature)
    })
  }
  return curvatures
}
