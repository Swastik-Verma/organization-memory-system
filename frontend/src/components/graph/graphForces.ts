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
