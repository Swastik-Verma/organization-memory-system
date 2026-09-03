import { useEffect, useMemo, useState } from 'react'
import { ClaimCard } from '@/components/entity/ClaimCard'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { claimTypeColor, claimTypeLabel } from '@/lib/claimTypes'
import { ApiErrorState } from '@/components/ApiErrorState'
import { fetchEntityClaims, isAbort } from '@/lib/api'
import type { ClaimResult } from '@/types/entity'

const CLAIM_TYPES = ['reports_to', 'works_with', 'negotiating_with', 'requests_from', 'informs']

type SortMode = 'confidence' | 'date'

interface ClaimsTabProps {
  entityId: string
}

export function ClaimsTab({ entityId }: ClaimsTabProps) {
  const [claims, setClaims] = useState<ClaimResult[] | null>(null)
  const [typeFilter, setTypeFilter] = useState<string | null>(null)
  const [sortMode, setSortMode] = useState<SortMode>('confidence')
  const [error, setError] = useState<unknown>(null)
  const [reloadToken, setReloadToken] = useState(0)

  // Type filtering is server-side (`c.claim_type = $claim_type` in the route's Cypher), so
  // changing the filter refetches rather than filtering the loaded array.
  useEffect(() => {
    const controller = new AbortController()
    setClaims(null)
    setError(null)
    fetchEntityClaims(entityId, typeFilter ?? undefined, { signal: controller.signal })
      .then((res) => setClaims(res.claims))
      .catch((err: unknown) => {
        if (!isAbort(err)) setError(err)
      })
    return () => controller.abort()
  }, [entityId, typeFilter, reloadToken])

  const sorted = useMemo(() => {
    if (!claims) return null
    const copy = [...claims]

    // The backend's own ORDER BY confidence DESC (entities.py's claims route) has no
    // secondary key, so ties come back in whatever order Neo4j happens to enumerate them —
    // which can change between requests. Each sort mode here breaks ties with the OTHER
    // axis, then falls back to claim_id (a stable, unique string) so the final order is
    // fully deterministic no matter what the backend returns.
    const byDateDesc = (a: ClaimResult, b: ClaimResult) =>
      (b.valid_from ?? '').localeCompare(a.valid_from ?? '')
    const byConfidenceDesc = (a: ClaimResult, b: ClaimResult) => b.confidence - a.confidence
    const byClaimIdDesc = (a: ClaimResult, b: ClaimResult) => b.claim_id.localeCompare(a.claim_id)

    if (sortMode === 'confidence') {
      copy.sort((a, b) => byConfidenceDesc(a, b) || byDateDesc(a, b) || byClaimIdDesc(a, b))
    } else {
      copy.sort((a, b) => byDateDesc(a, b) || byConfidenceDesc(a, b) || byClaimIdDesc(a, b))
    }
    return copy
  }, [claims, sortMode])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => setTypeFilter(null)}
            className={cn(
              'rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors',
              typeFilter === null ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:bg-muted/70',
            )}
          >
            All
          </button>
          {CLAIM_TYPES.map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => setTypeFilter(type)}
              className={cn(
                'rounded-full px-2.5 py-0.5 text-xs font-medium transition-opacity',
                claimTypeColor(type),
                typeFilter === type ? 'opacity-100 ring-2 ring-ring/50' : 'opacity-60 hover:opacity-100',
              )}
            >
              {claimTypeLabel(type)}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <span className="mr-1">Sort:</span>
          <Button
            type="button"
            size="sm"
            variant={sortMode === 'confidence' ? 'secondary' : 'ghost'}
            onClick={() => setSortMode('confidence')}
          >
            Confidence
          </Button>
          <Button type="button" size="sm" variant={sortMode === 'date' ? 'secondary' : 'ghost'} onClick={() => setSortMode('date')}>
            Date
          </Button>
        </div>
      </div>

      {error ? (
        <ApiErrorState error={error} onRetry={() => setReloadToken((n) => n + 1)} />
      ) : sorted === null ? (
        <div className="space-y-2">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : sorted.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          No claims match this filter.
        </p>
      ) : (
        <div className="space-y-2">
          {sorted.map((c) => (
            <ClaimCard key={c.claim_id} claim={c} currentEntityId={entityId} />
          ))}
        </div>
      )}
    </div>
  )
}
