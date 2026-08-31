import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import ForceGraph2D, { type ForceGraphMethods, type NodeObject } from 'react-force-graph-2d'
import type { GraphEdge, GraphNode } from '@/types/graph'
import { entityTypeColor } from '@/lib/entityTypes'
import {
  CHARGE_STRENGTH,
  EDGE_LABEL_FONT_PX,
  NODE_LABEL_FONT_PX,
  createCollisionForce,
  defaultZoomForNodeCount,
  estimateTextWidthPx,
  linkDistanceForScale,
  nodeRadius,
  truncateLabel,
} from './graphForces'
import { type TooltipController, type TooltipView, createTooltipController } from './tooltipController'
import { NodeTooltip } from './NodeTooltip'

interface GraphCanvasProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  expandedIds: Set<string>
  onExpandNode: (node: GraphNode) => void
  onNavigateNode: (node: GraphNode) => void
}

// Double-click delay: react-force-graph has no built-in dblclick event (see
// node_modules/force-graph/src/index.d.ts — onNodeClick only). A single click is
// deferred by this many ms; a second click on the same node within the window cancels
// the deferred single-click action and fires the double-click action instead.
const DOUBLE_CLICK_WINDOW_MS = 260

const RING_COLOR = '#4f46e5' // --primary, marks an already-expanded node
const EDGE_COLOR = '#1e293b' // dark slate, near-black — visible against the near-white background
const LABEL_COLOR = '#334155'
const LABEL_BG = 'rgba(255,255,255,0.88)'

type SimNode = GraphNode & { x?: number; y?: number }
type SimEdge = GraphEdge & { source: SimNode; target: SimNode; claim_count: number | null }

export function GraphCanvas({ nodes, edges, expandedIds, onExpandNode, onNavigateNode }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const fgRef = useRef<ForceGraphMethods<GraphNode, GraphEdge>>(undefined)
  const [size, setSize] = useState({ width: 0, height: 0 })
  const [hovered, setHovered] = useState<TooltipView | null>(null)
  const clickState = useRef<{ id: string; timer: number } | null>(null)
  const isReady = size.width > 0 && size.height > 0

  // Per-frame label decluttering. The collision force guarantees node labels never overlap
  // each other, but two edges can still cross near their midpoints, where their relationship
  // labels are drawn. Each frame this is seeded with every node label's box (node labels win
  // — they identify the entities) and then each edge label is drawn only if it lands in free
  // space. Coordinates are graph units, matching what the canvas render callbacks receive.
  const occupiedRef = useRef<Array<{ x0: number; y0: number; x1: number; y1: number }>>([])

  useLayoutEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      const { width, height } = entry.contentRect
      setSize({ width, height })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    return () => {
      if (clickState.current) window.clearTimeout(clickState.current.timer)
    }
  }, [])

  // The zoom force-graph picks depends on node count, and label footprints are measured in
  // screen pixels, so the collision force needs the current scale on every tick. Written in
  // the effect below (not during render) and read live by the force's closure.
  const scaleRef = useRef(defaultZoomForNodeCount(0))

  // NOTE: this effect must depend on `isReady`, not run once on mount. ForceGraph2D is only
  // rendered after the ResizeObserver reports a non-zero size, so on the very first render
  // fgRef.current is still undefined — an earlier version of this used `[]` deps, bailed out
  // on the undefined ref, and silently never configured any of these forces at all.
  // Re-running on nodes.length also re-tunes the link distance after a merge changes zoom.
  useEffect(() => {
    const fg = fgRef.current
    if (!isReady || !fg) return

    scaleRef.current = defaultZoomForNodeCount(nodes.length)
    fg.d3Force('charge')?.strength(CHARGE_STRENGTH)
    fg.d3Force('link')?.distance(linkDistanceForScale(scaleRef.current))
    fg.d3Force('collision', createCollisionForce(() => scaleRef.current))
    fg.d3ReheatSimulation()
  }, [isReady, nodes.length])

  const handleNodeClick = useCallback(
    (node: NodeObject<GraphNode>) => {
      const n = node as SimNode
      if (clickState.current && clickState.current.id === n.id) {
        window.clearTimeout(clickState.current.timer)
        clickState.current = null
        onNavigateNode(n)
        return
      }
      const timer = window.setTimeout(() => {
        clickState.current = null
        onExpandNode(n)
        if (fgRef.current && n.x != null && n.y != null) {
          fgRef.current.centerAt(n.x, n.y, 500)
        }
      }, DOUBLE_CLICK_WINDOW_MS)
      clickState.current = { id: n.id, timer }
    },
    [onExpandNode, onNavigateNode],
  )

  // The controller holds the hovered node internally rather than closing over React state,
  // so the tick/zoom handlers below can never act on a stale value — see tooltipController.ts
  // for the stuck-tooltip bug this prevents. Built in an effect because its projection
  // function reads fgRef, which is only legitimate outside of render.
  const tooltipRef = useRef<TooltipController | null>(null)
  useEffect(() => {
    tooltipRef.current = createTooltipController((node) => {
      const n = node as SimNode
      if (n.x == null || n.y == null) return null
      return fgRef.current?.graph2ScreenCoords(n.x, n.y) ?? { x: n.x, y: n.y }
    }, setHovered)
    return () => {
      tooltipRef.current = null
    }
  }, [])

  const handleNodeHover = useCallback((node: NodeObject<GraphNode> | null) => {
    // force-graph passes null when the pointer moves onto empty canvas, and the new node
    // when it moves straight from one node to another — both handled by hover().
    tooltipRef.current?.hover((node as GraphNode | null) ?? null)
  }, [])

  const handleBackgroundClick = useCallback(() => {
    tooltipRef.current?.clear()
  }, [])

  // Wired to onEngineTick/onZoom so the tooltip follows its node as the layout settles.
  // syncPosition only moves an already-showing tooltip; it can never resurrect one.
  const handleZoomOrPan = useCallback(() => {
    tooltipRef.current?.syncPosition()
  }, [])

  // A hovered node can be removed from the graph (e.g. a search replaces the view while the
  // pointer sits over a node). Nothing would fire a hover-out in that case.
  useEffect(() => {
    const controller = tooltipRef.current
    const current = controller?.current()
    if (controller && current && !nodes.some((n) => n.id === current.id)) {
      controller.clear()
    }
  }, [nodes])

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden bg-background">
      {size.width > 0 && size.height > 0 && (
        <ForceGraph2D<GraphNode, GraphEdge>
          ref={fgRef}
          width={size.width}
          height={size.height}
          graphData={{ nodes, links: edges }}
          nodeRelSize={1}
          onNodeClick={handleNodeClick}
          onNodeHover={handleNodeHover}
          onBackgroundClick={handleBackgroundClick}
          onZoom={handleZoomOrPan}
          onZoomEnd={handleZoomOrPan}
          onEngineTick={handleZoomOrPan}
          linkColor={() => EDGE_COLOR}
          linkWidth={(link) => {
            const claimCount = (link as SimEdge).claim_count
            return 1 + Math.min(claimCount ?? 1, 8) * 0.35
          }}
          onRenderFramePre={(ctx, globalScale) => {
            const fontSize = NODE_LABEL_FONT_PX / globalScale
            ctx.font = `${fontSize}px sans-serif`
            const boxes: Array<{ x0: number; y0: number; x1: number; y1: number }> = []
            for (const node of nodes) {
              const n = node as SimNode
              if (n.x == null || n.y == null) continue
              const r = nodeRadius(n.mention_count)
              const halfWidth = ctx.measureText(truncateLabel(n.label)).width / 2
              const top = n.y + r + 4 / globalScale
              boxes.push({ x0: n.x - halfWidth, y0: top, x1: n.x + halfWidth, y1: top + fontSize })
              // The circle itself is occupied space too — an edge label drawn across a node
              // is just as unreadable as one drawn across another label.
              boxes.push({ x0: n.x - r, y0: n.y - r, x1: n.x + r, y1: n.y + r })
            }
            occupiedRef.current = boxes
          }}
          linkCanvasObjectMode={() => 'after'}
          linkCanvasObject={(link, ctx, globalScale) => {
            const l = link as SimEdge
            if (l.source.x == null || l.source.y == null || l.target.x == null || l.target.y == null) return

            const dx = l.target.x - l.source.x
            const dy = l.target.y - l.source.y
            const linkLengthPx = Math.sqrt(dx * dx + dy * dy) * globalScale
            const text = l.type

            // Skip the relationship label when the edge is too short on screen to hold it —
            // drawing it anyway is what produced the unreadable pile-up of overlapping
            // "works_with" / "informs" text near tightly-packed nodes.
            if (linkLengthPx < estimateTextWidthPx(text, EDGE_LABEL_FONT_PX) * 1.4) return

            const midX = (l.source.x + l.target.x) / 2
            const midY = (l.source.y + l.target.y) / 2
            const fontSize = EDGE_LABEL_FONT_PX / globalScale
            ctx.font = `${fontSize}px sans-serif`
            ctx.textAlign = 'center'
            ctx.textBaseline = 'middle'
            const padding = 2 / globalScale
            const metrics = ctx.measureText(text)

            // Yield to any label already placed this frame (all node labels, plus edge
            // labels drawn earlier) rather than stacking text on text.
            const box = {
              x0: midX - metrics.width / 2 - padding,
              y0: midY - fontSize / 2 - padding,
              x1: midX + metrics.width / 2 + padding,
              y1: midY + fontSize / 2 + padding,
            }
            const collides = occupiedRef.current.some(
              (o) => box.x0 < o.x1 && o.x0 < box.x1 && box.y0 < o.y1 && o.y0 < box.y1,
            )
            if (collides) return
            occupiedRef.current.push(box)

            ctx.fillStyle = LABEL_BG
            ctx.fillRect(
              midX - metrics.width / 2 - padding,
              midY - fontSize / 2 - padding,
              metrics.width + padding * 2,
              fontSize + padding * 2,
            )
            ctx.fillStyle = LABEL_COLOR
            ctx.fillText(text, midX, midY)
          }}
          nodeCanvasObject={(node, ctx, globalScale) => {
            const n = node as SimNode
            if (n.x == null || n.y == null) return
            const r = nodeRadius(n.mention_count)

            ctx.beginPath()
            ctx.arc(n.x, n.y, r, 0, 2 * Math.PI)
            ctx.fillStyle = entityTypeColor(n.type)
            ctx.fill()

            if (expandedIds.has(n.id)) {
              ctx.lineWidth = 2.5
              ctx.strokeStyle = RING_COLOR
              ctx.stroke()
            }

            // Label sits below the circle, at a constant on-screen size. The backing chip
            // keeps it readable in the cases where a neighbour's edge still passes behind it.
            const fontSize = NODE_LABEL_FONT_PX / globalScale
            const text = truncateLabel(n.label)
            const labelY = n.y + r + 4 / globalScale
            ctx.font = `${fontSize}px sans-serif`
            ctx.textAlign = 'center'
            ctx.textBaseline = 'top'
            const padding = 2 / globalScale
            const metrics = ctx.measureText(text)
            ctx.fillStyle = LABEL_BG
            ctx.fillRect(
              n.x - metrics.width / 2 - padding,
              labelY - padding,
              metrics.width + padding * 2,
              fontSize + padding * 2,
            )
            ctx.fillStyle = LABEL_COLOR
            ctx.fillText(text, n.x, labelY)
          }}
          nodePointerAreaPaint={(node, color, ctx) => {
            const n = node as SimNode
            if (n.x == null || n.y == null) return
            ctx.fillStyle = color
            ctx.beginPath()
            ctx.arc(n.x, n.y, nodeRadius(n.mention_count), 0, 2 * Math.PI)
            ctx.fill()
          }}
        />
      )}
      {hovered && <NodeTooltip node={hovered.node} x={hovered.x} y={hovered.y} />}
    </div>
  )
}
