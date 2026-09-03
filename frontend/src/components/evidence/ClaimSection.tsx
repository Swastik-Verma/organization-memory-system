import { ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { claimTypeColor, claimTypeLabel } from '@/lib/claimTypes'
import type { EvidenceDetailResponse } from '@/types/evidence'

interface ClaimSectionProps {
  evidence: EvidenceDetailResponse
}

// Day 41: subject and object render as plain text, not links. EvidenceDetailResponse
// carries only subject_name / object_name — no ids — and no endpoint resolves a claim to
// its subject/object entity ids, so a link here could only be built from a fabricated id.
// The status badge and valid-from/valid-to fields are gone for the same reason: those live
// on the Claim node and evidence.py's Cypher never selects them. See types/evidence.ts.
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
        {evidence.claim_id && (
          <span className="font-mono text-xs text-muted-foreground">{evidence.claim_id}</span>
        )}
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2 text-base font-medium text-foreground">
        <span>{evidence.subject_name ?? 'Unknown'}</span>
        <ArrowRight className="size-4 shrink-0 text-muted-foreground" />
        <span>{evidence.object_name ?? 'Unknown'}</span>
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
      </div>
    </section>
  )
}
