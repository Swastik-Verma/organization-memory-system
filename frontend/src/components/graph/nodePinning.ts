// Hover pinning — holds a node (and its immediate neighbours) still while the pointer is
// over it, so the click target and tooltip anchor don't slide out from under the cursor.
//
// ── Why this is needed ────────────────────────────────────────────────────────────────
// The force simulation keeps adjusting positions while it settles, and every click-to-expand
// restarts it (force-graph calls resetCountdown() on every graphData change). On a dense
// graph that means the node you are aiming at is still drifting when you try to click it.
// Freezing the simulation after it settles (cooldownTicks in GraphCanvas.tsx) fixes the
// steady state; this fixes the window *before* it settles, which is exactly when a user is
// most likely to be reaching for a node that just appeared.
//
// ── How pinning works ─────────────────────────────────────────────────────────────────
// d3-force honours `fx`/`fy` on a node: when set, it overwrites x/y and zeroes velocity each
// tick, so the node is immovable while every other force still resolves around it. This
// matches force-graph's own drag implementation exactly — it pins with `fx = x; fy = y` and
// releases with `fx = undefined` (NOT null, and not `delete`), and on drag-end it only
// releases a node whose fx was undefined before the drag began. Following the same
// convention means a drag over a hover-pinned node composes correctly instead of fighting it.
//
// Lives in its own module rather than inside GraphCanvas.tsx for the same reason
// graphForces.ts and tooltipController.ts do: it is plain state over plain objects, so a
// test can drive the real implementation without a canvas or a DOM.

export interface PinnableNode {
  id: string
  x?: number
  y?: number
  fx?: number
  fy?: number
}

export interface PinnableEdge {
  source: string | { id: string }
  target: string | { id: string }
}

/** force-graph replaces a link's string endpoints with node object references once the
 *  simulation has initialised, so an endpoint can legitimately be either form. */
export function endpointId(endpoint: PinnableEdge['source']): string {
  return typeof endpoint === 'string' ? endpoint : endpoint.id
}

/** Ids directly connected to `nodeId` by at least one edge, excluding itself. */
export function neighbourIds(nodeId: string, edges: readonly PinnableEdge[]): Set<string> {
  const ids = new Set<string>()
  for (const edge of edges) {
    const source = endpointId(edge.source)
    const target = endpointId(edge.target)
    if (source === nodeId && target !== nodeId) ids.add(target)
    else if (target === nodeId && source !== nodeId) ids.add(source)
  }
  return ids
}

export interface PinController {
  /** Pin `node` and its immediate neighbours, releasing anything pinned by a prior call. */
  pinAround: (node: PinnableNode, nodes: readonly PinnableNode[], edges: readonly PinnableEdge[]) => void
  /** Release everything this controller pinned. Safe to call when nothing is pinned. */
  releaseAll: () => void
  /** Ids currently pinned by this controller — for assertions and debugging. */
  pinned: () => ReadonlySet<string>
}

export function createPinController(): PinController {
  // Node object REFERENCES, not ids: a node can leave the graph while pinned (a search
  // replaces the view mid-hover), and releasing it must still work. Holding the reference
  // means release never has to find the node in an array it may no longer be in.
  let pinnedNodes: PinnableNode[] = []

  function releaseAll() {
    for (const node of pinnedNodes) {
      // undefined, matching force-graph's own drag-release convention above. `delete` would
      // also work for d3, but keeping the property present-and-undefined matches how the
      // library checks it (`initPos.fx === undefined`).
      node.fx = undefined
      node.fy = undefined
    }
    pinnedNodes = []
  }

  function pinAround(
    node: PinnableNode,
    nodes: readonly PinnableNode[],
    edges: readonly PinnableEdge[],
  ) {
    releaseAll()

    const targets = neighbourIds(node.id, edges)
    targets.add(node.id)

    for (const candidate of nodes) {
      if (!targets.has(candidate.id)) continue
      // A node the simulation hasn't positioned yet has no x/y to freeze. Pinning it at
      // undefined would place it at NaN and fling it out of the viewport.
      if (candidate.x == null || candidate.y == null) continue
      candidate.fx = candidate.x
      candidate.fy = candidate.y
      pinnedNodes.push(candidate)
    }
  }

  return {
    pinAround,
    releaseAll,
    pinned: () => new Set(pinnedNodes.map((n) => n.id)),
  }
}
