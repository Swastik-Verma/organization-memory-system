import type { GraphNode } from '@/types/graph'
import { entityTypeColor, entityTypeLabel } from '@/lib/entityTypes'

interface NodeTooltipProps {
  node: GraphNode
  x: number
  y: number
}

// Positioned absolutely within GraphCanvas's relative container, in canvas-pixel
// coordinates (already converted from graph coordinates by the caller).
export function NodeTooltip({ node, x, y }: NodeTooltipProps) {
  return (
    <div
      className="pointer-events-none absolute z-10 min-w-40 rounded-md border border-border bg-popover px-3 py-2 text-popover-foreground shadow-md"
      style={{ left: x + 14, top: y + 14 }}
    >
      <div className="flex items-center gap-1.5">
        <span
          className="h-2 w-2 shrink-0 rounded-full"
          style={{ backgroundColor: entityTypeColor(node.type) }}
        />
        <span className="text-sm font-medium leading-tight">{node.label}</span>
      </div>
      <div className="mt-1 text-xs text-muted-foreground">
        {entityTypeLabel(node.type)} · {node.mention_count} mention{node.mention_count === 1 ? '' : 's'}
      </div>
    </div>
  )
}
