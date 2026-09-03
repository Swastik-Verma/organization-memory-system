import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiErrorState } from '@/components/ApiErrorState'
import { EntityHeader } from '@/components/entity/EntityHeader'
import { ClaimsTab } from '@/components/entity/ClaimsTab'
import { RelationshipsTab } from '@/components/entity/RelationshipsTab'
import { TimelineTab } from '@/components/entity/TimelineTab'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ApiError, fetchEntityClaims, fetchEntityDetail, isAbort } from '@/lib/api'
import type { EntityDetailResponse, EntityStats } from '@/types/entity'

/**
 * The header's claim count and first/last-seen dates are not on EntityDetailResponse — they
 * are derived here from the entity's own claims.
 *
 * This deliberately uses the SAME unfiltered call the Claims tab renders, so the "N claims"
 * in the header and the number of cards in the tab are the same number by construction,
 * rather than two independently-sourced figures that can drift apart.
 */
function deriveStats(claims: { valid_from: string | null }[], total: number): EntityStats {
  const dates = claims
    .map((c) => c.valid_from)
    .filter((d): d is string => Boolean(d))
    .sort()
  return {
    claim_count: total,
    first_seen: dates[0] ?? null,
    last_seen: dates[dates.length - 1] ?? null,
  }
}

export function EntityDetailPage() {
  const { id: rawId } = useParams<{ id: string }>()
  // Route params arrive percent-encoded because entity ids contain colons. Everything in
  // this component (state, comparisons, props to tabs) uses the decoded id; the api client
  // re-encodes it at the network boundary.
  const id = rawId ? decodeURIComponent(rawId) : ''

  const [entity, setEntity] = useState<EntityDetailResponse | null>(null)
  const [stats, setStats] = useState<EntityStats | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [reloadToken, setReloadToken] = useState(0)

  const retry = useCallback(() => setReloadToken((n) => n + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    setEntity(null)
    setStats(null)
    setError(null)

    fetchEntityDetail(id, { signal: controller.signal })
      .then(setEntity)
      .catch((err: unknown) => {
        if (!isAbort(err)) setError(err)
      })

    // Stats load independently of the header — a failure here leaves the page usable with
    // the counts showing as still-loading rather than taking down the whole entity view.
    fetchEntityClaims(id, undefined, { signal: controller.signal })
      .then((res) => setStats(deriveStats(res.claims, res.total)))
      .catch(() => {
        /* non-fatal: header simply keeps its placeholder */
      })

    return () => controller.abort()
  }, [id, reloadToken])

  if (error) {
    const notFound = error instanceof ApiError && error.kind === 'notfound'
    return (
      <div className="space-y-4">
        <Link to="/entities" className="text-sm text-muted-foreground hover:text-foreground">
          &larr; Back to Entities
        </Link>
        <ApiErrorState
          error={error}
          onRetry={retry}
          notFoundMessage={
            notFound
              ? `No entity with id "${id}" exists in the graph. Note that only Person and Organization entities are available here — Deals and Decisions can be found in the Graph Explorer.`
              : undefined
          }
        />
      </div>
    )
  }

  if (!entity) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <EntityHeader entity={entity} stats={stats} />

      <Tabs defaultValue="claims">
        <TabsList>
          <TabsTrigger value="claims">Claims</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="relationships">Relationships</TabsTrigger>
        </TabsList>
        <TabsContent value="claims">
          <ClaimsTab entityId={entity.id} />
        </TabsContent>
        <TabsContent value="timeline">
          <TimelineTab entityId={entity.id} />
        </TabsContent>
        <TabsContent value="relationships">
          <RelationshipsTab entityId={entity.id} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
