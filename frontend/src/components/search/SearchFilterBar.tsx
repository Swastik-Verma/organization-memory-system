import { cn } from '@/lib/utils'
import { CLAIM_TYPE_LABELS } from '@/lib/claimTypes'
import { SEARCH_TYPE_FILTER_LABELS, SEARCH_TYPE_ORDER, searchTypeBadgeClass } from '@/lib/searchTypes'
import type { SearchResultType } from '@/types/search'

const CLAIM_TYPES = Object.keys(CLAIM_TYPE_LABELS)

interface SearchFilterBarProps {
  type: SearchResultType | null
  onTypeChange: (type: SearchResultType | null) => void
  claimType: string
  onClaimTypeChange: (claimType: string) => void
  dateFrom: string
  onDateFromChange: (date: string) => void
  dateTo: string
  onDateToChange: (date: string) => void
  minConfidence: string
  onMinConfidenceChange: (value: string) => void
}

// claim_type only makes sense when Claims can appear in the results; date range and
// confidence only make sense when Claims or Evidence can appear — per the Day 45 brief.
function showClaimTypeFilter(type: SearchResultType | null) {
  return type === null || type === 'claim'
}

function showDateAndConfidenceFilters(type: SearchResultType | null) {
  return type === null || type === 'claim' || type === 'evidence'
}

const inputClass =
  'h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50'

export function SearchFilterBar({
  type,
  onTypeChange,
  claimType,
  onClaimTypeChange,
  dateFrom,
  onDateFromChange,
  dateTo,
  onDateToChange,
  minConfidence,
  onMinConfidenceChange,
}: SearchFilterBarProps) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap justify-center gap-1.5">
        <button
          type="button"
          onClick={() => onTypeChange(null)}
          className={cn(
            'rounded-full px-3 py-1 text-xs font-medium transition-colors',
            type === null ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:bg-muted/70',
          )}
        >
          All
        </button>
        {SEARCH_TYPE_ORDER.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => onTypeChange(t)}
            className={cn(
              'rounded-full px-3 py-1 text-xs font-medium transition-opacity',
              searchTypeBadgeClass(t),
              type === t ? 'opacity-100 ring-2 ring-ring/50' : 'opacity-60 hover:opacity-100',
            )}
          >
            {SEARCH_TYPE_FILTER_LABELS[t]}
          </button>
        ))}
      </div>

      {(showClaimTypeFilter(type) || showDateAndConfidenceFilters(type)) && (
        <div className="flex flex-wrap items-center justify-center gap-3">
          {showClaimTypeFilter(type) && (
            <select
              value={claimType}
              onChange={(e) => onClaimTypeChange(e.target.value)}
              className={inputClass}
              aria-label="Filter by claim type"
            >
              <option value="">All claim types</option>
              {CLAIM_TYPES.map((ct) => (
                <option key={ct} value={ct}>
                  {CLAIM_TYPE_LABELS[ct]}
                </option>
              ))}
            </select>
          )}

          {showDateAndConfidenceFilters(type) && (
            <>
              <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                From
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => onDateFromChange(e.target.value)}
                  className={inputClass}
                  aria-label="Date from"
                />
              </label>
              <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                To
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => onDateToChange(e.target.value)}
                  className={inputClass}
                  aria-label="Date to"
                />
              </label>
              <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                Min confidence
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.1}
                  value={minConfidence}
                  onChange={(e) => onMinConfidenceChange(e.target.value)}
                  placeholder="0.0"
                  className={cn(inputClass, 'w-20')}
                  aria-label="Minimum confidence"
                />
              </label>
            </>
          )}
        </div>
      )}
    </div>
  )
}
