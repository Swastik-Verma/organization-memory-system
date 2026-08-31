import type { GraphNode } from '@/types/graph'

// Hover-tooltip state, deliberately kept out of React state and out of the canvas component
// so it can be tested without a browser.
//
// The bug this design exists to prevent: the tooltip used to be a single piece of React
// state holding BOTH which node is hovered and where to draw it, and the engine-tick handler
// re-asserted that state on every tick to keep the tooltip pinned to a moving node. Clicking
// a node to expand it reheats the simulation, so ticks fire continuously for seconds; moving
// the mouse to blank space cleared the tooltip exactly once, and the very next tick — running
// a closure captured while a node was still hovered — put it straight back. The restored
// value was then captured by the next render's closure, so it re-asserted itself forever and
// the tooltip was stuck permanently.
//
// The rule that fixes it: only hover/clear events may change WHICH node is showing. Position
// sync may only move a tooltip that is already showing — never create or revive one. Because
// the controller keeps identity in a plain variable rather than a captured closure value,
// `syncPosition` always reads the current truth and can never operate on a stale one.

export interface TooltipView {
  node: GraphNode
  x: number
  y: number
}

/** Projects a node's graph coordinates to screen pixels; null if it isn't positioned yet. */
export type ProjectNode = (node: GraphNode) => { x: number; y: number } | null

export interface TooltipController {
  /** A node is hovered (or null when the pointer leaves onto empty canvas). */
  hover: (node: GraphNode | null) => void
  /** Hide the tooltip outright — background clicks, and nodes leaving the graph. */
  clear: () => void
  /** Re-project the currently-showing tooltip. A no-op when nothing is showing. */
  syncPosition: () => void
  /** The node currently showing a tooltip, for callers that need to check. */
  current: () => GraphNode | null
}

export function createTooltipController(
  project: ProjectNode,
  onChange: (view: TooltipView | null) => void,
): TooltipController {
  let currentNode: GraphNode | null = null

  function emit() {
    if (!currentNode) {
      onChange(null)
      return
    }
    const point = project(currentNode)
    if (!point) {
      // Positioned nowhere yet — keep the identity, but don't draw a tooltip at a
      // meaningless coordinate.
      onChange(null)
      return
    }
    onChange({ node: currentNode, x: point.x, y: point.y })
  }

  return {
    hover(node) {
      // Covers all three transitions the same way: node → null (leaving onto empty canvas),
      // node → different node (swap), null → node (entering).
      if (node === currentNode) {
        emit()
        return
      }
      currentNode = node
      emit()
    },

    clear() {
      currentNode = null
      onChange(null)
    },

    syncPosition() {
      // The critical guard: never revives a cleared tooltip, and never invents one.
      if (!currentNode) return
      emit()
    },

    current() {
      return currentNode
    },
  }
}
