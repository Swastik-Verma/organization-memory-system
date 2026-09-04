import { memo } from 'react'
import { ArrowDown, ArrowUp, ArrowUpDown, Undo2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { mergeStatusColor, mergeStatusLabel, phaseColor, phaseLabel, strategyColor, strategyLabel } from '@/lib/mergeTypes'
import type { SortDir, SortKey } from '@/lib/mergeFilter'
import type { MergeItem } from '@/types/merge'

interface MergeTableProps {
  merges: MergeItem[]
  sortKey: SortKey
  sortDir: SortDir
  onSort: (key: SortKey) => void
  onUndoClick: (merge: MergeItem) => void
}

function Pill({ className, children }: { className: string; children: React.ReactNode }) {
  return (
    <span className={cn('inline-flex w-fit items-center rounded-full px-2.5 py-0.5 text-xs font-medium', className)}>
      {children}
    </span>
  )
}

function formatDate(timestamp: string): string {
  return new Date(timestamp).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'source_name', label: 'Source Entity' },
  { key: 'target_name', label: 'Target Entity' },
  { key: 'strategy', label: 'Strategy' },
  { key: 'confidence', label: 'Confidence' },
  { key: 'phase', label: 'Phase' },
  { key: 'status', label: 'Status' },
  { key: 'timestamp', label: 'Date' },
]

// memo() is load-bearing, not a micro-optimisation. This table renders one <tr> per merge —
// up to 3,315 of them, each with 8 cells, 3 badge pills and (on fuzzy rows) a button with an
// icon. Re-rendering it costs ~1.9s in jsdom / a very visible stall in a browser. Without
// memo, every keystroke in the page's search box re-renders this whole table even when the
// row list is unchanged, which is what made typing lag. It only works because MergesPage
// keeps all five props referentially stable between keystrokes — see the comments there.
export const MergeTable = memo(function MergeTable({
  merges,
  sortKey,
  sortDir,
  onSort,
  onUndoClick,
}: MergeTableProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
            {COLUMNS.map((col) => (
              <th key={col.key} className="px-3 py-2 font-medium">
                <button
                  type="button"
                  onClick={() => onSort(col.key)}
                  className="inline-flex items-center gap-1 hover:text-foreground"
                >
                  {col.label}
                  {sortKey === col.key ? (
                    sortDir === 'asc' ? (
                      <ArrowUp className="size-3" />
                    ) : (
                      <ArrowDown className="size-3" />
                    )
                  ) : (
                    <ArrowUpDown className="size-3 opacity-40" />
                  )}
                </button>
              </th>
            ))}
            <th className="px-3 py-2 font-medium">Action</th>
          </tr>
        </thead>
        <tbody>
          {merges.map((merge, i) => (
            <tr
              key={merge.merge_id ?? `exact-${merge.target_id}-${merge.source_name}-${i}`}
              className="border-b border-border/60 last:border-0 hover:bg-muted/20"
            >
              <td className="px-3 py-2 text-foreground">{merge.source_name}</td>
              <td className="px-3 py-2 text-foreground">{merge.target_name}</td>
              <td className="px-3 py-2">
                <Pill className={strategyColor(merge.strategy)}>{strategyLabel(merge.strategy)}</Pill>
              </td>
              <td className="px-3 py-2 tabular-nums text-foreground">
                {Math.round(merge.confidence * 100)}%
              </td>
              <td className="px-3 py-2">
                <Pill className={phaseColor(merge.phase)}>{phaseLabel(merge.phase)}</Pill>
              </td>
              <td className="px-3 py-2">
                <Pill className={mergeStatusColor(merge.status)}>{mergeStatusLabel(merge.status)}</Pill>
              </td>
              <td className="px-3 py-2 whitespace-nowrap text-muted-foreground">
                {formatDate(merge.timestamp)}
              </td>
              <td className="px-3 py-2">
                {merge.undoable ? (
                  <Button type="button" variant="destructive" size="xs" onClick={() => onUndoClick(merge)}>
                    <Undo2 className="size-3" />
                    Undo
                  </Button>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
})
