import { type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface GraphControlsProps {
  query: string
  onQueryChange: (value: string) => void
  onSubmitSearch: () => void
  isSearching: boolean
  searchError: string | null
  hops: 1 | 2
  onHopsChange: (hops: 1 | 2) => void
  onReset: () => void
}

export function GraphControls({
  query,
  onQueryChange,
  onSubmitSearch,
  isSearching,
  searchError,
  hops,
  onHopsChange,
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
            Click a node to expand its neighborhood. Double-click to view its full profile.
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

        <div className="flex items-center gap-1 rounded-lg border border-border p-0.5">
          <Button
            type="button"
            size="sm"
            variant={hops === 1 ? 'default' : 'ghost'}
            onClick={() => onHopsChange(1)}
            aria-pressed={hops === 1}
          >
            1 hop
          </Button>
          <Button
            type="button"
            size="sm"
            variant={hops === 2 ? 'default' : 'ghost'}
            onClick={() => onHopsChange(2)}
            aria-pressed={hops === 2}
          >
            2 hops
          </Button>
        </div>

        <Button type="button" variant="outline" onClick={onReset}>
          Reset
        </Button>
      </div>

      {searchError && <p className="mt-2 text-sm text-destructive">{searchError}</p>}
    </div>
  )
}
