import { useEffect, useMemo, useState } from 'react'
import { ClaimCard } from '@/components/entity/ClaimCard'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { claimTypeColor, claimTypeLabel } from '@/lib/claimTypes'
import { mockFetchEntityClaims } from '@/mocks/entityMocks'
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

  useEffect(() => {
    let cancelled = false
    setClaims(null)
    mockFetchEntityClaims(entityId, typeFilter ?? undefined).then((res) => {
      if (!cancelled) setClaims(res.claims)
    })
    return () => {
      cancelled = true
    }
  }, [entityId, typeFilter])

  const sorted = useMemo(() => {
    if (!claims) return null
    const copy = [...claims]
    if (sortMode === 'confidence') {
      copy.sort((a, b) => b.confidence - a.confidence)
    } else {
      copy.sort((a, b) => (b.valid_from ?? '').localeCompare(a.valid_from ?? ''))
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

      {sorted === null ? (
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
