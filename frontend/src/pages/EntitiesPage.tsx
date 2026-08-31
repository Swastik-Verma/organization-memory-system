import { useEffect, useState } from 'react'
import { EntityCard } from '@/components/entity/EntityCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { entityTypeBadgeClass, entityTypeLabel } from '@/lib/entityTypes'
import { mockFetchEntities } from '@/mocks/entityMocks'
import type { EntityListItem } from '@/types/entity'

const ENTITY_TYPES = ['person', 'organization', 'deal', 'decision']
const PAGE_SIZE = 10

export function EntitiesPage() {
  const [typeFilter, setTypeFilter] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [skip, setSkip] = useState(0)

  const [entities, setEntities] = useState<EntityListItem[] | null>(null)
  const [total, setTotal] = useState(0)

  // Filtering/search reset the page back to the start rather than leaving the user on a
  // page number that might no longer exist for the new result set. Bundled into the same
  // handler as the filter/search change itself (rather than a separate effect watching
  // them) so the fetch effect below only ever runs once per user action, not twice with a
  // stale intermediate page number in between.
  function selectType(type: string | null) {
    setTypeFilter(type)
    setSkip(0)
  }

  function updateSearch(value: string) {
    setSearch(value)
    setSkip(0)
  }

  useEffect(() => {
    let cancelled = false
    setEntities(null)
    mockFetchEntities({ type: typeFilter ?? undefined, search, skip, limit: PAGE_SIZE }).then((res) => {
      if (cancelled) return
      setEntities(res.entities)
      setTotal(res.total)
    })
    return () => {
      cancelled = true
    }
  }, [typeFilter, search, skip])

  const page = Math.floor(skip / PAGE_SIZE) + 1
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="space-y-6">
      <div className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Entities</h1>
        <p className="text-sm text-muted-foreground">Browse extracted entities from the Enron corpus</p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => selectType(null)}
            className={cn(
              'rounded-full px-3 py-1 text-xs font-medium transition-colors',
              typeFilter === null ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:bg-muted/70',
            )}
          >
            All
          </button>
          {ENTITY_TYPES.map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => selectType(type)}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium transition-opacity',
                entityTypeBadgeClass(type),
                typeFilter === type ? 'opacity-100 ring-2 ring-ring/50' : 'opacity-60 hover:opacity-100',
              )}
            >
              {entityTypeLabel(type)}
            </button>
          ))}
        </div>

        <Input
          value={search}
          onChange={(e) => updateSearch(e.target.value)}
          placeholder="Search entities by name..."
          className="w-full sm:w-64"
        />
      </div>

      {entities === null ? (
        <div className="space-y-2">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : entities.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          No entities found matching your search.
        </p>
      ) : (
        <div className="space-y-2">
          {entities.map((entity) => (
            <EntityCard key={entity.id} entity={entity} />
          ))}
        </div>
      )}

      {entities !== null && total > PAGE_SIZE && (
        <div className="flex items-center justify-between pt-2">
          <p className="text-xs text-muted-foreground">
            Page {page} of {pageCount} &middot; {total} entities
          </p>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={skip === 0}
              onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
            >
              Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={skip + PAGE_SIZE >= total}
              onClick={() => setSkip(skip + PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
