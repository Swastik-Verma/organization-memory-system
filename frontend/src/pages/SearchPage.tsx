import { useEffect, useState } from 'react'
import { Search as SearchIcon } from 'lucide-react'
import { ApiErrorState } from '@/components/ApiErrorState'
import { SearchBar } from '@/components/search/SearchBar'
import { SearchFilterBar } from '@/components/search/SearchFilterBar'
import { SearchResultGroupSection } from '@/components/search/SearchResultGroupSection'
import { Skeleton } from '@/components/ui/skeleton'
import { globalSearch, isAbort } from '@/lib/api'
import type { GlobalSearchResponse, SearchResultType } from '@/types/search'

// Same debounce pattern as Days 39/43/44's search boxes, at the 250ms the Day 45 brief asks
// for specifically (those pages use 300ms — page-specific, not a shared constant).
const SEARCH_DEBOUNCE_MS = 250

function activeFilterSummary(args: {
  type: SearchResultType | null
  claimType: string
  dateFrom: string
  dateTo: string
  minConfidence: string
}): string | null {
  const parts: string[] = []
  if (args.type) parts.push(`type: ${args.type}`)
  if (args.claimType) parts.push(`claim type: ${args.claimType}`)
  if (args.dateFrom) parts.push(`from: ${args.dateFrom}`)
  if (args.dateTo) parts.push(`to: ${args.dateTo}`)
  if (args.minConfidence) parts.push(`min confidence: ${args.minConfidence}`)
  return parts.length ? parts.join(', ') : null
}

export function SearchPage() {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')

  const [type, setType] = useState<SearchResultType | null>(null)
  const [claimType, setClaimType] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [minConfidence, setMinConfidence] = useState('')

  const [response, setResponse] = useState<GlobalSearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query), SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [query])

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setResponse(null)
      setError(null)
      setLoading(false)
      return
    }

    const controller = new AbortController()
    setLoading(true)
    setError(null)

    const confidenceValue = minConfidence === '' ? undefined : Number(minConfidence)

    globalSearch(
      {
        q: debouncedQuery,
        type: type ?? undefined,
        claim_type: claimType || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        min_confidence: confidenceValue,
      },
      { signal: controller.signal },
    )
      .then((res) => setResponse(res))
      .catch((err: unknown) => {
        if (isAbort(err)) return
        setError(err)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })

    return () => controller.abort()
  }, [debouncedQuery, type, claimType, dateFrom, dateTo, minConfidence, reloadToken])

  const hasSearched = debouncedQuery.trim().length > 0
  const filterSummary = activeFilterSummary({ type, claimType, dateFrom, dateTo, minConfidence })

  return (
    <div className="space-y-6">
      <div className="space-y-1.5 text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Search</h1>
        <p className="text-sm text-muted-foreground">Search across entities, claims, and evidence</p>
      </div>

      <SearchBar value={query} onChange={setQuery} loading={loading} />

      <SearchFilterBar
        type={type}
        onTypeChange={setType}
        claimType={claimType}
        onClaimTypeChange={setClaimType}
        dateFrom={dateFrom}
        onDateFromChange={setDateFrom}
        dateTo={dateTo}
        onDateToChange={setDateTo}
        minConfidence={minConfidence}
        onMinConfidenceChange={setMinConfidence}
      />

      <div className="mx-auto max-w-5xl">
        {!hasSearched ? (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border px-4 py-16 text-center">
            <SearchIcon className="size-8 text-muted-foreground" />
            <p className="max-w-md text-sm text-muted-foreground">
              Search across all entities, claims, and evidence in the knowledge graph.
            </p>
          </div>
        ) : error ? (
          <ApiErrorState error={error} onRetry={() => setReloadToken((n) => n + 1)} />
        ) : loading && response === null ? (
          <div className="space-y-6">
            <div className="space-y-2.5">
              <Skeleton className="h-4 w-24" />
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            </div>
            <div className="space-y-2.5">
              <Skeleton className="h-4 w-24" />
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            </div>
          </div>
        ) : response && response.total_results === 0 ? (
          <div className="rounded-lg border border-dashed border-border px-4 py-16 text-center">
            <p className="text-sm font-medium text-foreground">
              No results found for &ldquo;{response.query}&rdquo;
            </p>
            {filterSummary && (
              <p className="mt-1.5 text-xs text-muted-foreground">Active filters: {filterSummary}</p>
            )}
          </div>
        ) : response ? (
          <div className="space-y-6">
            {response.groups.map((group) => (
              <SearchResultGroupSection key={group.type} group={group} query={debouncedQuery} />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}
