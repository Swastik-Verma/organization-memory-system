// The 1-hop / 2-hop toggle was removed on Day 41. Every subgraph request is now single-hop:
// a 2-hop neighbourhood of a well-connected person runs to hundreds of nodes and is
// unreadable, and the backend's depth=2 query LIMITs before it has enumerated the claim
// paths, so it returns an arbitrary slice rather than a bigger version of the same graph.
// Deliberate scope reduction, not a bug.
import { type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface GraphControlsProps {
  query: string
  onQueryChange: (value: string) => void
  onSubmitSearch: () => void
  isSearching: boolean
  searchError: string | null
  onReset: () => void
}

export function GraphControls({
  query,
  onQueryChange,
  onSubmitSearch,
  isSearching,
  searchError,
  onReset,
}: GraphControlsProps) {
  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    onSubmitSearch()
  }

  return (
    <div className="shrink-0 border-b border-border px-6 py-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Graph Explorer</h1>
          <p className="text-sm text-muted-foreground">
            Click a node to expand its neighborhood. Double-click to open its profile in a
            new tab. Arrows point from subject to object; undirected lines are mutual.
          </p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <form onSubmit={handleSubmit} className="flex min-w-64 flex-1 items-center gap-2">
          <Input
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Search for an entity to start exploring…"
            aria-label="Search for an entity"
          />
          <Button type="submit" size="default" disabled={isSearching || query.trim().length === 0}>
            {isSearching ? 'Searching…' : 'Search'}
          </Button>
        </form>

        <Button type="button" variant="outline" onClick={onReset}>
          Reset
        </Button>
      </div>

      {searchError && <p className="mt-2 text-sm text-destructive">{searchError}</p>}
    </div>
  )
}
