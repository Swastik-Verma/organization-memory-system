import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { EntityHeader } from '@/components/entity/EntityHeader'
import { ClaimsTab } from '@/components/entity/ClaimsTab'
import { RelationshipsTab } from '@/components/entity/RelationshipsTab'
import { TimelineTab } from '@/components/entity/TimelineTab'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { mockFetchEntityDetail } from '@/mocks/entityMocks'
import type { EntityDetailResponse } from '@/types/entity'

export function EntityDetailPage() {
  const { id: rawId } = useParams<{ id: string }>()
  const id = rawId ? decodeURIComponent(rawId) : ''

  const [entity, setEntity] = useState<EntityDetailResponse | null>(null)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    let cancelled = false
    setEntity(null)
    setNotFound(false)

    mockFetchEntityDetail(id)
      .then((res) => {
        if (!cancelled) setEntity(res)
      })
      .catch(() => {
        if (!cancelled) setNotFound(true)
      })

    return () => {
      cancelled = true
    }
  }, [id])

  if (notFound) {
    return (
      <div className="space-y-4">
        <Link to="/entities" className="text-sm text-muted-foreground hover:text-foreground">
          &larr; Back to Entities
        </Link>
        <p className="rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          Entity "{id}" was not found.
        </p>
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
      <EntityHeader entity={entity} />

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
