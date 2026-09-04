import { useCallback, useEffect, useMemo, useState } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'
import { ApiErrorState } from '@/components/ApiErrorState'
import { Skeleton } from '@/components/ui/skeleton'
import { MergeFilterBar } from '@/components/merges/MergeFilterBar'
import { MergeTable } from '@/components/merges/MergeTable'
import { UndoMergeDialog } from '@/components/merges/UndoMergeDialog'
import { fetchMerges, isAbort, undoMerge } from '@/lib/api'
import { filterAndSortMerges, type SortDir, type SortKey } from '@/lib/mergeFilter'
import type { MergeItem } from '@/types/merge'

type PhaseFilter = 'all' | 'exact' | 'fuzzy'
type StatusFilter = 'all' | 'active' | 'undone'

/**
 * The search box filters client-side over every loaded row, but it is debounced anyway.
 *
 * The filtering itself is cheap (~3ms over all 3,315 rows). What is expensive is that a new
 * search value re-renders MergeTable, and that table has one row per merge — measured at
 * ~1.9s for a full 3,315-row render in jsdom, and clearly visible as input lag in a browser.
 * Because the input is a controlled component, the typed character cannot paint until that
 * render commits, so the lag lands on the input itself rather than on the table.
 *
 * Debouncing means at most one such render per typing pause instead of one per keystroke.
 * 250ms, matching the value asked for; EntitiesPage.tsx uses 300ms for its server-side search.
 */
const SEARCH_DEBOUNCE_MS = 250

interface Banner {
  kind: 'success' | 'error'
  message: string
}

export function MergesPage() {
  const [phase, setPhase] = useState<PhaseFilter>('all')
  const [status, setStatus] = useState<StatusFilter>('all')
  const [strategy, setStrategy] = useState('all')
  // `search` drives the input (updates on every keystroke, so typing always feels instant);
  // `debouncedSearch` drives the filtering and therefore the table's re-render.
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  const [merges, setMerges] = useState<MergeItem[] | null>(null)
  const [serverTotal, setServerTotal] = useState(0)
  const [error, setError] = useState<unknown>(null)
  const [reloadToken, setReloadToken] = useState(0)

  // Grand totals for the page subtitle, captured from the first (unfiltered) load and left
  // alone afterward — GET /api/merges computes exact_count/fuzzy_count/total AFTER applying
  // the phase/status/strategy filters, so those fields only describe the *current* filtered
  // view. The subtitle wants the whole audit log's shape regardless of what's filtered.
  const [baseline, setBaseline] = useState<{ total: number; exact: number; fuzzy: number } | null>(
    null,
  )

  // Sort key and direction live in ONE state object so a single, dependency-free useCallback
  // can update both. Two separate setState calls would need the current key in scope, which
  // would make the handler a new function on every render and defeat MergeTable's memo().
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({
    key: 'timestamp',
    dir: 'desc',
  })

  const [undoTarget, setUndoTarget] = useState<MergeItem | null>(null)
  const [undoSubmitting, setUndoSubmitting] = useState(false)
  const [banner, setBanner] = useState<Banner | null>(null)

  const isUnfiltered = phase === 'all' && status === 'all' && strategy === 'all'

  useEffect(() => {
    const controller = new AbortController()
    setMerges(null)
    setError(null)

    fetchMerges(
      {
        phase: phase === 'all' ? undefined : phase,
        status: status === 'all' ? undefined : status,
        strategy: strategy === 'all' ? undefined : strategy,
      },
      { signal: controller.signal },
    )
      .then((res) => {
        setMerges(res.merges)
        setServerTotal(res.total)
        if (isUnfiltered) {
          setBaseline({ total: res.total, exact: res.exact_count, fuzzy: res.fuzzy_count })
        }
      })
      .catch((err: unknown) => {
        if (!isAbort(err)) setError(err)
      })

    return () => controller.abort()
  }, [phase, status, strategy, reloadToken, isUnfiltered])

  // Keeps the input responsive: typing only updates `search` (a tiny re-render of the filter
  // bar); the table's data — and therefore its expensive re-render — is recomputed once the
  // user pauses.
  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search), SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [search])

  // Deliberately keyed on `debouncedSearch`, NOT `search` — this array's identity is what
  // MergeTable's memo() compares, so it must not change on every keystroke.
  const visibleMerges = useMemo(
    () => (merges ? filterAndSortMerges(merges, debouncedSearch, sort.key, sort.dir) : []),
    [merges, debouncedSearch, sort],
  )

  const handleSort = useCallback((key: SortKey) => {
    setSort((prev) =>
      prev.key === key ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' },
    )
  }, [])

  async function handleConfirmUndo() {
    if (!undoTarget?.merge_id) return
    setUndoSubmitting(true)
    try {
      const res = await undoMerge(undoTarget.merge_id)
      setBanner({ kind: 'success', message: res.message })
      setUndoTarget(null)
      setReloadToken((n) => n + 1)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Undo failed for an unknown reason.'
      setBanner({ kind: 'error', message })
      setUndoTarget(null)
    } finally {
      setUndoSubmitting(false)
    }
  }

  const subtitle = baseline
    ? `Entity resolution decisions — ${baseline.exact.toLocaleString()} exact matches + ${baseline.fuzzy.toLocaleString()} fuzzy matches`
    : 'Entity resolution decisions'

  return (
    <div className="space-y-6">
      <div className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Merge Audit Log</h1>
        <p className="text-sm text-muted-foreground">{subtitle}</p>
      </div>

      {banner && (
        <div
          className={
            'flex items-start justify-between gap-3 rounded-lg border px-3 py-2 text-sm ' +
            (banner.kind === 'success'
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
              : 'border-destructive/30 bg-destructive/10 text-destructive')
          }
        >
          <div className="flex items-start gap-2">
            {banner.kind === 'success' ? (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
            ) : (
              <XCircle className="mt-0.5 size-4 shrink-0" />
            )}
            <span>{banner.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setBanner(null)}
            className="shrink-0 text-xs font-medium underline-offset-2 hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      <MergeFilterBar
        phase={phase}
        onPhaseChange={setPhase}
        status={status}
        onStatusChange={setStatus}
        strategy={strategy}
        onStrategyChange={setStrategy}
        search={search}
        onSearchChange={setSearch}
      />

      {error ? (
        <ApiErrorState error={error} onRetry={() => setReloadToken((n) => n + 1)} />
      ) : merges === null ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : visibleMerges.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          No merges match your filters.
        </p>
      ) : (
        <MergeTable
          merges={visibleMerges}
          sortKey={sort.key}
          sortDir={sort.dir}
          onSort={handleSort}
          onUndoClick={setUndoTarget}
        />
      )}

      {!error && merges !== null && (
        <p className="text-xs text-muted-foreground">
          Showing {visibleMerges.length.toLocaleString()} of {serverTotal.toLocaleString()} merges
        </p>
      )}

      <UndoMergeDialog
        merge={undoTarget}
        submitting={undoSubmitting}
        onCancel={() => setUndoTarget(null)}
        onConfirm={handleConfirmUndo}
      />
    </div>
  )
}
