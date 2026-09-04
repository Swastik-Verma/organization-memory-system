import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { strategyLabel } from '@/lib/mergeTypes'

// The real, closed set of strategies the Day 16/17 resolution pipeline produces — confirmed
// live against GET /api/merges, not the Day 43 brief's list (which names "middle_initial"
// and "domain_match"; the backend has no merges of the former and spells the latter
// "same_domain"). Hardcoded rather than derived from the loaded page's data so the dropdown
// doesn't shrink when a phase/status filter narrows the current result set.
const STRATEGIES = ['email_match', 'normalized_name_match', 'fuzzy', 'nickname', 'same_domain']

type PhaseFilter = 'all' | 'exact' | 'fuzzy'
type StatusFilter = 'all' | 'active' | 'undone'

interface MergeFilterBarProps {
  phase: PhaseFilter
  onPhaseChange: (phase: PhaseFilter) => void
  status: StatusFilter
  onStatusChange: (status: StatusFilter) => void
  strategy: string
  onStrategyChange: (strategy: string) => void
  search: string
  onSearchChange: (search: string) => void
}

function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
}) {
  return (
    <div className="inline-flex gap-1 rounded-lg bg-muted p-0.5">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
            value === opt.value
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

export function MergeFilterBar({
  phase,
  onPhaseChange,
  status,
  onStatusChange,
  strategy,
  onStrategyChange,
  search,
  onSearchChange,
}: MergeFilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <SegmentedControl
        value={phase}
        onChange={onPhaseChange}
        options={[
          { value: 'all', label: 'All' },
          { value: 'exact', label: 'Exact' },
          { value: 'fuzzy', label: 'Fuzzy' },
        ]}
      />
      <SegmentedControl
        value={status}
        onChange={onStatusChange}
        options={[
          { value: 'all', label: 'All' },
          { value: 'active', label: 'Active' },
          { value: 'undone', label: 'Undone' },
        ]}
      />
      <select
        value={strategy}
        onChange={(e) => onStrategyChange(e.target.value)}
        className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <option value="all">All strategies</option>
        {STRATEGIES.map((s) => (
          <option key={s} value={s}>
            {strategyLabel(s)}
          </option>
        ))}
      </select>
      <div className="relative ml-auto w-full sm:w-64">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search source or target name..."
          className="pl-8"
        />
      </div>
    </div>
  )
}
