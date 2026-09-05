import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'
import { ApiErrorState } from '@/components/ApiErrorState'
import { Skeleton } from '@/components/ui/skeleton'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ConflictCard } from '@/components/conflicts/ConflictCard'
import { ConflictFilterBar } from '@/components/conflicts/ConflictFilterBar'
import { AutoResolvedCard } from '@/components/conflicts/AutoResolvedCard'
import { KeepBestDialog } from '@/components/conflicts/KeepBestDialog'
import { ConfirmResolveDialog, type SimpleResolveAction } from '@/components/conflicts/ConfirmResolveDialog'
import { fetchConflictGroups, fetchConflictResolutions, isAbort, resolveConflict } from '@/lib/api'
import { filterConflictResolutions, filterConflicts, type ConflictStatusFilter } from '@/lib/conflictFilter'
import type {
  ConflictGroup,
  ConflictGroupListResponse,
  ConflictResolutionListResponse,
} from '@/types/conflict'

// Same 250ms debounce as MergesPage.tsx's search box. Both tabs here are small lists (14 and
// 13 rows today), so a full re-render on every keystroke is cheap — but every filter/search
// input in this app debounces from the start regardless of list size, so behavior stays
// consistent across pages and neither tab needs re-visiting if either count ever grows.
const SEARCH_DEBOUNCE_MS = 250

interface Banner {
  kind: 'success' | 'error'
  message: string
}

export function ConflictsPage() {
  const [tab, setTab] = useState<'needs_review' | 'auto_resolved'>('needs_review')

  // ---- Needs Review (GET /api/conflict-groups) — human review queue, unchanged from before
  // this session's Auto-Resolved tab was added. ----
  const [status, setStatus] = useState<ConflictStatusFilter>('all')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  const [data, setData] = useState<ConflictGroupListResponse | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [reloadToken, setReloadToken] = useState(0)

  const [keepBestTarget, setKeepBestTarget] = useState<ConflictGroup | null>(null)
  const [confirmTarget, setConfirmTarget] = useState<{
    conflict: ConflictGroup
    action: SimpleResolveAction
  } | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [banner, setBanner] = useState<Banner | null>(null)

  // ---- Auto-Resolved (GET /api/conflict-resolutions) — read-only audit trail, no dialogs,
  // no submitting state, no banner: there is nothing here a human action could produce. ----
  const [autoResolvedData, setAutoResolvedData] = useState<ConflictResolutionListResponse | null>(null)
  const [autoResolvedError, setAutoResolvedError] = useState<unknown>(null)
  const [autoResolvedReloadToken, setAutoResolvedReloadToken] = useState(0)
  const [autoResolvedSearch, setAutoResolvedSearch] = useState('')
  const [autoResolvedDebouncedSearch, setAutoResolvedDebouncedSearch] = useState('')

  // Both endpoints are fetched on mount regardless of which tab is active — the tab labels
  // need real counts from both responses immediately, not just whichever tab happens to be open.
  useEffect(() => {
    const controller = new AbortController()
    setData(null)
    setError(null)
    fetchConflictGroups({ signal: controller.signal })
      .then(setData)
      .catch((err: unknown) => {
        if (!isAbort(err)) setError(err)
      })
    return () => controller.abort()
  }, [reloadToken])

  useEffect(() => {
    const controller = new AbortController()
    setAutoResolvedData(null)
    setAutoResolvedError(null)
    fetchConflictResolutions({ signal: controller.signal })
      .then(setAutoResolvedData)
      .catch((err: unknown) => {
        if (!isAbort(err)) setAutoResolvedError(err)
      })
    return () => controller.abort()
  }, [autoResolvedReloadToken])

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search), SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [search])

  useEffect(() => {
    const timer = window.setTimeout(() => setAutoResolvedDebouncedSearch(autoResolvedSearch), SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [autoResolvedSearch])

  const visible = useMemo(
    () => (data ? filterConflicts(data.conflicts, status, debouncedSearch) : []),
    [data, status, debouncedSearch],
  )

  const visibleAutoResolved = useMemo(
    () => (autoResolvedData ? filterConflictResolutions(autoResolvedData.conflicts, autoResolvedDebouncedSearch) : []),
    [autoResolvedData, autoResolvedDebouncedSearch],
  )

  async function submitResolve(
    conflict: ConflictGroup,
    action: 'keep_one' | SimpleResolveAction,
    winningClaimId?: string,
  ) {
    setSubmitting(true)
    try {
      const res = await resolveConflict(conflict.conflict_id, action, winningClaimId)
      setBanner({ kind: 'success', message: res.message })
      setKeepBestTarget(null)
      setConfirmTarget(null)
      setReloadToken((n) => n + 1)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Resolution failed for an unknown reason.'
      setBanner({ kind: 'error', message })
    } finally {
      setSubmitting(false)
    }
  }

  // Fallbacks (14 / 13) match the counts already confirmed live, shown only until each
  // endpoint's own response arrives — same placeholder-then-replace pattern the Needs Review
  // subtitle already used before this tab existed.
  const needsReviewCount = data ? data.total : 14
  const autoResolvedCount = autoResolvedData ? autoResolvedData.total : 13

  return (
    <div className="space-y-6">
      <div className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Conflict Review Queue</h1>
        <p className="text-sm text-muted-foreground">
          Contradicting claims flagged for human review, and temporal conflicts the system
          resolved automatically.
        </p>
      </div>

      <Tabs value={tab} onValueChange={(v) => setTab(v as 'needs_review' | 'auto_resolved')}>
        <TabsList>
          <TabsTrigger value="needs_review">Needs Review ({needsReviewCount})</TabsTrigger>
          <TabsTrigger value="auto_resolved">Auto-Resolved ({autoResolvedCount})</TabsTrigger>
        </TabsList>

        <TabsContent value="needs_review" className="space-y-6 pt-4">
          {data && (
            <p className="text-sm text-muted-foreground">
              {data.needs_review} unresolved, {data.resolved} resolved
            </p>
          )}

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

          <ConflictFilterBar status={status} onStatusChange={setStatus} search={search} onSearchChange={setSearch} />

          {error ? (
            <ApiErrorState error={error} onRetry={() => setReloadToken((n) => n + 1)} />
          ) : data === null ? (
            <div className="space-y-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-56 w-full" />
              ))}
            </div>
          ) : visible.length === 0 ? (
            <p className="rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
              No conflicts match your filters.
            </p>
          ) : (
            <div className="space-y-4">
              {visible.map((conflict) => (
                <ConflictCard
                  key={conflict.conflict_id}
                  conflict={conflict}
                  onKeepBest={setKeepBestTarget}
                  onAllHistorical={(c) => setConfirmTarget({ conflict: c, action: 'all_historical' })}
                  onDismiss={(c) => setConfirmTarget({ conflict: c, action: 'dismiss' })}
                />
              ))}
            </div>
          )}

          {!error && data !== null && (
            <div className="space-y-1 text-xs text-muted-foreground">
              <p>
                Showing {visible.length.toLocaleString()} of {data.total.toLocaleString()} conflicts.
              </p>
              <p>
                The Health dashboard&rsquo;s &ldquo;Conflict Pairs&rdquo; count is higher than the
                total here by design — it counts individual contradicting claim pairs, while this
                page groups those pairs into one card per subject + relationship type.
              </p>
            </div>
          )}
        </TabsContent>

        <TabsContent value="auto_resolved" className="space-y-6 pt-4">
          <p className="text-sm text-muted-foreground">
            Read-only audit trail — the system ordered these claims chronologically on its own;
            no human action is needed or possible here.
          </p>

          <Input
            value={autoResolvedSearch}
            onChange={(e) => setAutoResolvedSearch(e.target.value)}
            placeholder="Search by subject name..."
            className="sm:w-64"
          />

          {autoResolvedError ? (
            <ApiErrorState
              error={autoResolvedError}
              onRetry={() => setAutoResolvedReloadToken((n) => n + 1)}
            />
          ) : autoResolvedData === null ? (
            <div className="space-y-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-40 w-full" />
              ))}
            </div>
          ) : visibleAutoResolved.length === 0 ? (
            <p className="rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
              No conflicts match your search.
            </p>
          ) : (
            <div className="space-y-4">
              {visibleAutoResolved.map((conflict) => (
                <AutoResolvedCard key={conflict.conflict_id} conflict={conflict} />
              ))}
            </div>
          )}

          {!autoResolvedError && autoResolvedData !== null && (
            <p className="text-xs text-muted-foreground">
              Showing {visibleAutoResolved.length.toLocaleString()} of{' '}
              {autoResolvedData.total.toLocaleString()} auto-resolved conflicts.
            </p>
          )}
        </TabsContent>
      </Tabs>

      <KeepBestDialog
        conflict={keepBestTarget}
        submitting={submitting}
        onCancel={() => setKeepBestTarget(null)}
        onConfirm={(winningClaimId) =>
          keepBestTarget && submitResolve(keepBestTarget, 'keep_one', winningClaimId)
        }
      />
      <ConfirmResolveDialog
        conflict={confirmTarget?.conflict ?? null}
        action={confirmTarget?.action ?? null}
        submitting={submitting}
        onCancel={() => setConfirmTarget(null)}
        onConfirm={() => confirmTarget && submitResolve(confirmTarget.conflict, confirmTarget.action)}
      />
    </div>
  )
}
