import { CheckCircle2, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { claimTypeColor, claimTypeLabel } from '@/lib/claimTypes'
import { classificationColor, classificationLabel, resolutionColor, resolutionLabel } from '@/lib/conflictTypes'
import { sharedDates } from '@/lib/conflictFilter'
import { Pill, formatConflictDate as formatDate } from '@/components/conflicts/shared'
import type { ConflictGroup } from '@/types/conflict'

interface ConflictCardProps {
  conflict: ConflictGroup
  onKeepBest: (conflict: ConflictGroup) => void
  onAllHistorical: (conflict: ConflictGroup) => void
  onDismiss: (conflict: ConflictGroup) => void
}

export function ConflictCard({ conflict, onKeepBest, onAllHistorical, onDismiss }: ConflictCardProps) {
  const needsReview = conflict.resolution === 'needs_review'
  const highlightedDates = sharedDates(conflict.claims)

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="border-b border-border p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-base font-semibold">
            {/* Same direct-link approach as the object names below — subject_id is a real
                entity id (person:.../org:...), reachable via /api/entities/{id}. */}
            <a
              href={`/entities/${encodeURIComponent(conflict.subject_id)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              {conflict.subject_name}
            </a>
          </h3>
          <Pill className={claimTypeColor(conflict.claim_type)}>{claimTypeLabel(conflict.claim_type)}</Pill>
          <Pill className={classificationColor(conflict.classification)}>
            {classificationLabel(conflict.classification)}
          </Pill>
          <Pill className={resolutionColor(conflict.resolution)}>{resolutionLabel(conflict.resolution)}</Pill>
        </div>
        <p className="mt-1.5 text-xs text-muted-foreground">{conflict.reason}</p>
      </div>

      <div className="overflow-x-auto p-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted-foreground">
              <th className="pb-2 pr-3 font-medium">Reports To</th>
              <th className="pb-2 pr-3 font-medium">Date</th>
              <th className="pb-2 pr-3 font-medium">Confidence</th>
              <th className="pb-2 pr-3 font-medium">Mentions</th>
              <th className="pb-2 font-medium">Evidence</th>
            </tr>
          </thead>
          <tbody>
            {conflict.claims.map((c) => {
              const isWinner = conflict.current_claim_id === c.claim_id
              const dateIsShared = c.valid_from !== null && highlightedDates.has(c.valid_from)
              return (
                <tr key={c.claim_id} className="border-t border-border/60">
                  <td className="py-2 pr-3">
                    {/* object_id is a real entity id in the same format used by every other
                        route in this app (person:.../org:...) — reports_to's object is always
                        a Person or Organization, both reachable via /api/entities/{id} (Day 39
                        gotcha), so this links directly rather than falling back to a
                        name-based /entities?search= link. */}
                    <a
                      href={`/entities/${encodeURIComponent(c.object_id)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      {c.object_name}
                    </a>
                    {isWinner && (
                      <Pill className="ml-2 bg-green-100 text-green-700">
                        <CheckCircle2 className="mr-1 size-3" />
                        Current
                      </Pill>
                    )}
                  </td>
                  <td className="py-2 pr-3">
                    <span
                      className={cn(
                        'rounded px-1.5 py-0.5',
                        dateIsShared && 'bg-amber-100 font-medium text-amber-800',
                      )}
                    >
                      {formatDate(c.valid_from)}
                    </span>
                  </td>
                  <td className="py-2 pr-3 tabular-nums text-foreground">
                    {Math.round(c.confidence * 100)}%
                  </td>
                  <td className="py-2 pr-3 tabular-nums text-foreground">{c.mention_count}</td>
                  <td className="py-2 text-foreground">
                    {c.evidence_id ? (
                      <>
                        <a
                          href={`/evidence/${encodeURIComponent(c.evidence_id)}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          title="View evidence"
                          aria-label="View evidence"
                          className="inline-flex items-center gap-1 text-primary hover:underline"
                        >
                          <FileText className="size-3.5" />
                        </a>
                        {c.evidence_count > 1 && (
                          <p className="text-[11px] text-muted-foreground">
                            +{c.evidence_count - 1} more evidence sources
                          </p>
                        )}
                      </>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {needsReview && (
        <div className="flex flex-wrap gap-2 border-t border-border p-4">
          <Button type="button" onClick={() => onKeepBest(conflict)}>
            Keep Best
          </Button>
          <Button
            type="button"
            variant="outline"
            className="border-amber-300 text-amber-700 hover:bg-amber-50"
            onClick={() => onAllHistorical(conflict)}
          >
            All Historical
          </Button>
          <Button type="button" variant="outline" onClick={() => onDismiss(conflict)}>
            Dismiss
          </Button>
        </div>
      )}
    </div>
  )
}
