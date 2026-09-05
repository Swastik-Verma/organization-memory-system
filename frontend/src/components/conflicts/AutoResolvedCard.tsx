import { CheckCircle2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { classificationColor, classificationLabel, resolutionColor, resolutionLabel } from '@/lib/conflictTypes'
import { Pill, formatConflictDate } from '@/components/conflicts/shared'
import type { ConflictResolutionGroup } from '@/types/conflict'

interface AutoResolvedCardProps {
  conflict: ConflictResolutionGroup
}

/**
 * Read-only audit-trail card for one temporal-succession conflict the system resolved on its
 * own — no action buttons, no resolution logic (unlike ConflictCard.tsx's human-review cards).
 * Claims arrive from the backend already sorted chronologically ascending, so this renders them
 * top-to-bottom as a vertical timeline (same visual language as
 * src/components/entity/TimelineTab.tsx's border-l + dot pattern) rather than inventing a
 * separate arrow-chain style — the last entry is always the current claim.
 */
export function AutoResolvedCard({ conflict }: AutoResolvedCardProps) {
  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="border-b border-border p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-base font-semibold">
            <a
              href={`/entities/${encodeURIComponent(conflict.subject_id)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              {conflict.subject_name}
            </a>
          </h3>
          <Pill className={classificationColor(conflict.classification)}>
            {classificationLabel(conflict.classification)}
          </Pill>
          <Pill className={resolutionColor(conflict.resolution)}>{resolutionLabel(conflict.resolution)}</Pill>
        </div>
        <p className="mt-1.5 text-xs text-muted-foreground">{conflict.reason}</p>
      </div>

      <div className="p-4">
        <div className="relative space-y-5 border-l border-border pl-6">
          {conflict.claims.map((c) => {
            const isCurrent = c.claim_id === conflict.current_claim_id
            return (
              <div key={c.claim_id} className="relative">
                <span
                  className={cn(
                    'absolute top-1 -left-[1.6rem] size-2.5 rounded-full border-2 border-background',
                    isCurrent ? 'bg-green-600' : 'bg-muted-foreground/50',
                  )}
                />
                <div className="flex flex-wrap items-center gap-2">
                  <a
                    href={`/entities/${encodeURIComponent(c.object_id)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={cn(
                      'font-medium hover:underline',
                      isCurrent ? 'text-primary' : 'text-primary/60 line-through decoration-primary/40',
                    )}
                  >
                    {c.object_name}
                  </a>
                  <span className="text-xs text-muted-foreground">{formatConflictDate(c.valid_from)}</span>
                  {isCurrent ? (
                    <Pill className="bg-green-100 text-green-700">
                      <CheckCircle2 className="mr-1 size-3" />
                      Current
                    </Pill>
                  ) : (
                    <Pill className="bg-muted text-muted-foreground">Superseded</Pill>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
