import { CheckCircle2 } from 'lucide-react'

interface AttentionNeededCardProps {
  pendingReview: number | null
  conflictPairs: number
}

const CONFLICTS_HREF = '/conflicts'

export function AttentionNeededCard({ pendingReview, conflictPairs }: AttentionNeededCardProps) {
  const allClear = pendingReview === 0 && conflictPairs === 0

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="mb-3 text-xs font-medium text-muted-foreground">Attention Needed</p>

      {allClear ? (
        <div className="flex items-center gap-2 rounded-md bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700">
          <CheckCircle2 className="size-4" />
          All clear
        </div>
      ) : (
        <div className="space-y-2">
          <a
            href={CONFLICTS_HREF}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-accent/50"
          >
            <span className="text-foreground">Pending Review</span>
            <span className="font-semibold tabular-nums text-foreground">
              {pendingReview === null ? '—' : pendingReview.toLocaleString()}
            </span>
          </a>
          <a
            href={CONFLICTS_HREF}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-accent/50"
          >
            <span className="text-foreground">Conflict Pairs</span>
            <span className="font-semibold tabular-nums text-foreground">
              {conflictPairs.toLocaleString()}
            </span>
          </a>
        </div>
      )}
    </div>
  )
}
