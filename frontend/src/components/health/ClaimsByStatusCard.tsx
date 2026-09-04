import { claimStatusColor, claimStatusLabel } from '@/lib/claimTypes'

interface ClaimsByStatusCardProps {
  claimsByStatus: Record<string, number>
}

export function ClaimsByStatusCard({ claimsByStatus }: ClaimsByStatusCardProps) {
  const entries = Object.entries(claimsByStatus).sort((a, b) => b[1] - a[1])

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="mb-3 text-xs font-medium text-muted-foreground">Claims by Status</p>
      <div className="space-y-2">
        {entries.map(([status, count]) => (
          <div key={status} className="flex items-center justify-between">
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${claimStatusColor(status)}`}
            >
              {claimStatusLabel(status)}
            </span>
            <span className="text-sm font-medium tabular-nums text-foreground">
              {count.toLocaleString()}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
