import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { claimStatusColor, claimStatusLabel, claimTypeColor, claimTypeLabel } from '@/lib/claimTypes'
import type { EvidenceDetailResponse } from '@/types/evidence'

interface ClaimSectionProps {
  evidence: EvidenceDetailResponse
}

// The claim subject/object link to /entities/:id and open in a new tab — this page is
// itself typically reached by opening a link in a new tab (see the Day 40 pre-task fix to
// EvidenceDrawer.tsx / ClaimCard.tsx), so a further click here shouldn't lose that tab too.
export function ClaimSection({ evidence }: ClaimSectionProps) {
  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span
          className={cn(
            'inline-flex w-fit items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
            claimTypeColor(evidence.claim_type ?? ''),
          )}
        >
          {claimTypeLabel(evidence.claim_type ?? '')}
        </span>
        <span
          className={cn(
            'inline-flex w-fit items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
            claimStatusColor(evidence.status),
          )}
        >
          {claimStatusLabel(evidence.status)}
        </span>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2 text-base font-medium text-foreground">
        <Link
          to={`/entities/${encodeURIComponent(evidence.subject_id)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          {evidence.subject_name}
        </Link>
        <ArrowRight className="size-4 shrink-0 text-muted-foreground" />
        <Link
          to={`/entities/${encodeURIComponent(evidence.object_id)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          {evidence.object_name}
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-4 text-xs text-muted-foreground sm:grid-cols-3">
        <div>
          <p className="mb-1">Confidence</p>
          <div className="flex items-center gap-1.5">
            <div className="h-1.5 w-16 rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${Math.round((evidence.confidence ?? 0) * 100)}%` }}
              />
            </div>
            <span>{Math.round((evidence.confidence ?? 0) * 100)}%</span>
          </div>
        </div>
        <div>
          <p className="mb-1">Valid from</p>
          <p className="text-foreground">{evidence.valid_from ?? 'Unknown'}</p>
        </div>
        <div>
          <p className="mb-1">Valid to</p>
          <p className="text-foreground">{evidence.valid_to ?? 'Present'}</p>
        </div>
      </div>
    </section>
  )
}
