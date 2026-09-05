import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import type { ConflictStatusFilter } from '@/lib/conflictFilter'

interface ConflictFilterBarProps {
  status: ConflictStatusFilter
  onStatusChange: (status: ConflictStatusFilter) => void
  search: string
  onSearchChange: (search: string) => void
}

const STATUS_OPTIONS: { value: ConflictStatusFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'needs_review', label: 'Needs Review' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'dismissed', label: 'Dismissed' },
]

// Same segmented-control shape as MergeFilterBar.tsx's local component — kept as its own
// small copy here rather than extracted to a shared file, matching that file's precedent.
function SegmentedControl({
  value,
  onChange,
}: {
  value: ConflictStatusFilter
  onChange: (value: ConflictStatusFilter) => void
}) {
  return (
    <div className="inline-flex gap-1 rounded-lg bg-muted p-0.5">
      {STATUS_OPTIONS.map((opt) => (
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

export function ConflictFilterBar({
  status,
  onStatusChange,
  search,
  onSearchChange,
}: ConflictFilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <SegmentedControl value={status} onChange={onStatusChange} />
      <div className="relative ml-auto w-full sm:w-64">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search by subject name..."
          className="pl-8"
        />
      </div>
    </div>
  )
}
