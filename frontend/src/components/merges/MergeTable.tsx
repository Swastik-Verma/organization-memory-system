import { memo, useCallback, useRef, useState } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronDown, ChevronRight, Undo2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { fetchMergeDetail, isAbort } from '@/lib/api'
import {
  mergeStatusColor,
  mergeStatusLabel,
  phaseColor,
  phaseLabel,
  strategyColor,
  strategyLabel,
} from '@/lib/mergeTypes'
import { MergeDetailPanel, type DetailStatus } from '@/components/merges/MergeDetailPanel'
import type { SortDir, SortKey } from '@/lib/mergeFilter'
import type { MergeDetailResponse, MergeItem } from '@/types/merge'

interface MergeTableProps {
  merges: MergeItem[]
  sortKey: SortKey
  sortDir: SortDir
  onSort: (key: SortKey) => void
  onUndoClick: (merge: MergeItem) => void
}

interface DetailState {
  status: DetailStatus
  data?: MergeDetailResponse
  error?: string
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

// One leading column for the expand chevron, one trailing column for the Undo action —
// everything in between mirrors COLUMNS above, in the same order.
const GRID_COLS = '28px minmax(140px,1.3fr) minmax(140px,1.3fr) 130px 100px 84px 84px 110px 96px'

// Real HTML table rows can't be absolutely positioned for virtualization (browsers ignore
// `position` on <tr>, since row layout is computed by the table algorithm, not the box
// model) — that's why this is a CSS-grid-based layout instead of <table>/<tr>/<td>. ARIA
// roles below restore the semantics a real table would otherwise give for free.
const ESTIMATED_ROW_HEIGHT = 52
const TABLE_MAX_HEIGHT = 'calc(100vh - 250px)'

function rowKey(merge: MergeItem, index: number): string {
  return merge.merge_id ?? `exact-${merge.target_id}-${merge.source_name}-${index}`
}

// memo() is load-bearing, not a micro-optimisation — see the Day 43 log's search-lag
// writeup. It only works because MergesPage keeps all five props referentially stable
// between keystrokes. Virtualization (Day 46) means this component now also renders only
// the ~20-30 rows in view rather than all 3,315, which is what actually keeps a full
// re-render (e.g. after clearing a search) cheap; memo() and virtualization solve two
// different costs (unnecessary re-renders vs. an inherently large necessary one) and both
// are needed.
export const MergeTable = memo(function MergeTable({
  merges,
  sortKey,
  sortDir,
  onSort,
  onUndoClick,
}: MergeTableProps) {
  const parentRef = useRef<HTMLDivElement>(null)

  // Expand state and the detail cache live here, inside MergeTable, rather than being lifted
  // to MergesPage — that keeps expanding a row from ever re-rendering the page (which would
  // reopen the exact search-lag risk the memo() above exists to prevent), and it survives
  // virtualization recycling the visible row set since MergeTable itself never unmounts
  // while the page is open.
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => new Set())
  const [details, setDetails] = useState<Map<string, DetailState>>(() => new Map())

  const rowVirtualizer = useVirtualizer({
    count: merges.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ESTIMATED_ROW_HEIGHT,
    overscan: 8,
    getItemKey: (index) => rowKey(merges[index], index),
  })

  const toggleExpand = useCallback(
    (merge: MergeItem) => {
      const id = merge.merge_id
      if (!id) return

      setExpandedIds((prev) => {
        const next = new Set(prev)
        if (next.has(id)) next.delete(id)
        else next.add(id)
        return next
      })

      // Already cached (success), already failed (error), or already in flight (loading) —
      // re-collapsing and re-expanding must not re-fetch.
      if (details.has(id)) return

      setDetails((prev) => new Map(prev).set(id, { status: 'loading' }))
      fetchMergeDetail(id)
        .then((data) => {
          setDetails((prev) => new Map(prev).set(id, { status: 'success', data }))
        })
        .catch((err: unknown) => {
          if (isAbort(err)) return
          const message = err instanceof Error ? err.message : 'Failed to load merge details.'
          setDetails((prev) => new Map(prev).set(id, { status: 'error', error: message }))
        })
    },
    [details],
  )

  return (
    <div className="rounded-lg border border-border" role="table" aria-label="Merge audit log">
      <div
        className="grid items-center gap-2 border-b border-border bg-muted/40 px-3 py-2 text-left text-xs text-muted-foreground"
        style={{ gridTemplateColumns: GRID_COLS }}
        role="row"
      >
        <span aria-hidden="true" />
        {COLUMNS.map((col) => (
          <span key={col.key} role="columnheader">
            <button
              type="button"
              onClick={() => onSort(col.key)}
              className="inline-flex items-center gap-1 font-medium hover:text-foreground"
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
          </span>
        ))}
        <span className="font-medium" role="columnheader">
          Action
        </span>
      </div>

      <div ref={parentRef} className="overflow-y-auto" style={{ maxHeight: TABLE_MAX_HEIGHT }}>
        <div style={{ height: rowVirtualizer.getTotalSize(), position: 'relative' }}>
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const merge = merges[virtualRow.index]
            const id = merge.merge_id
            const isExpandable = merge.phase === 'fuzzy' && !!id
            const isExpanded = !!id && expandedIds.has(id)
            const detailState = id ? details.get(id) : undefined

            return (
              <div
                key={virtualRow.key}
                data-index={virtualRow.index}
                ref={rowVirtualizer.measureElement}
                className="absolute top-0 left-0 w-full border-b border-border/60 last:border-0"
                style={{ transform: `translateY(${virtualRow.start}px)` }}
                role="row"
              >
                <div
                  className={cn(
                    'grid items-center gap-2 px-3 py-2 text-sm hover:bg-muted/20',
                    isExpandable && 'cursor-pointer',
                  )}
                  style={{ gridTemplateColumns: GRID_COLS }}
                  onClick={isExpandable ? () => toggleExpand(merge) : undefined}
                >
                  <span className="flex justify-center text-muted-foreground" role="cell">
                    {isExpandable ? (
                      isExpanded ? (
                        <ChevronDown className="size-3.5" />
                      ) : (
                        <ChevronRight className="size-3.5" />
                      )
                    ) : null}
                  </span>
                  <span className="truncate text-foreground" role="cell">
                    {merge.source_name}
                  </span>
                  <span className="truncate text-foreground" role="cell">
                    {merge.target_name}
                  </span>
                  <span role="cell">
                    <Pill className={strategyColor(merge.strategy)}>{strategyLabel(merge.strategy)}</Pill>
                  </span>
                  <span className="tabular-nums text-foreground" role="cell">
                    {Math.round(merge.confidence * 100)}%
                  </span>
                  <span role="cell">
                    <Pill className={phaseColor(merge.phase)}>{phaseLabel(merge.phase)}</Pill>
                  </span>
                  <span role="cell">
                    <Pill className={mergeStatusColor(merge.status)}>{mergeStatusLabel(merge.status)}</Pill>
                  </span>
                  <span className="whitespace-nowrap text-muted-foreground" role="cell">
                    {formatDate(merge.timestamp)}
                  </span>
                  <span role="cell" onClick={(e) => e.stopPropagation()}>
                    {merge.undoable ? (
                      <Button type="button" variant="destructive" size="xs" onClick={() => onUndoClick(merge)}>
                        <Undo2 className="size-3" />
                        Undo
                      </Button>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </span>
                </div>

                {isExpanded && detailState && (
                  <div className="border-t border-border/60 bg-muted/10 px-4" onClick={(e) => e.stopPropagation()}>
                    <MergeDetailPanel
                      status={detailState.status}
                      sourceSnapshot={detailState.data?.source_snapshot}
                      targetSnapshot={detailState.data?.target_snapshot}
                      errorMessage={detailState.error}
                    />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
})
