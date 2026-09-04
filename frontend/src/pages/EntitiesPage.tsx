import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { EntityCard } from '@/components/entity/EntityCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { entityTypeBadgeClass, entityTypeLabel } from '@/lib/entityTypes'
import { ApiErrorState } from '@/components/ApiErrorState'
import { fetchEntities, isAbort } from '@/lib/api'
import type { EntityListItem } from '@/types/entity'

// Only person and organization. GET /api/entities matches `(n:Person) OR (n:Organization)`
// and its entity_type param understands only those two strings — passing "deal" or
// "decision" does NOT filter or error, it silently falls through to the unfiltered branch
// and returns all 21,729 person+org entities mislabelled as a Deal/Decision result. Deal
// and Decision nodes are genuinely unreachable through this endpoint; they are searchable
// via /api/graph/search and appear in the Graph Explorer instead. (Backend gap — flagged,
// not worked around; see CLAUDE.md §5.)
const ENTITY_TYPES = ['person', 'organization']
const PAGE_SIZE = 10
// The search box now hits the server on every keystroke, so it waits for a pause in typing
// rather than firing a request per character (Day 39 deferred this while the mock was local).
const SEARCH_DEBOUNCE_MS = 300

export function EntitiesPage() {
  // Day 42: the health dashboard's "Top Mentioned Entities" table links here as
  // `/entities?search=<name>` (it has no real entity id to link to directly, only a
  // Person's name from the health report). Read that once on mount so the link actually
  // pre-fills the search box instead of landing on an unfiltered list.
  const [searchParams] = useSearchParams()
  const initialSearch = searchParams.get('search') ?? ''

  const [typeFilter, setTypeFilter] = useState<string | null>(null)
  const [search, setSearch] = useState(initialSearch)
  const [skip, setSkip] = useState(0)

  const [debouncedSearch, setDebouncedSearch] = useState(initialSearch)

  const [entities, setEntities] = useState<EntityListItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [error, setError] = useState<unknown>(null)
  const [reloadToken, setReloadToken] = useState(0)

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
    const timer = window.setTimeout(() => setDebouncedSearch(search), SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [search])

  useEffect(() => {
    const controller = new AbortController()
    setEntities(null)
    setError(null)

    fetchEntities(
      { type: typeFilter ?? undefined, search: debouncedSearch, skip, limit: PAGE_SIZE },
      { signal: controller.signal },
    )
      .then((res) => {
        setEntities(res.entities)
        setTotal(res.total)
      })
      .catch((err: unknown) => {
        if (isAbort(err)) return
        setError(err)
      })

    return () => controller.abort()
  }, [typeFilter, debouncedSearch, skip, reloadToken])

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

      {error ? (
        <ApiErrorState error={error} onRetry={() => setReloadToken((n) => n + 1)} />
      ) : entities === null ? (
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

      {!error && entities !== null && total > PAGE_SIZE && (
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
