import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { claimStatusColor, claimStatusLabel, claimTypeColor, claimTypeLabel } from '@/lib/claimTypes'
import type { ClaimResult } from '@/types/entity'

interface ClaimCardProps {
  claim: ClaimResult
  /** The entity whose page this card is rendered on — that side renders as plain text. */
  currentEntityId: string
}

function EntityRef({ id, name, isCurrent }: { id: string; name: string; isCurrent: boolean }) {
  if (isCurrent) {
    return <span className="font-medium text-foreground">{name}</span>
  }
  return (
    <Link to={`/entities/${encodeURIComponent(id)}`} className="font-medium text-primary hover:underline">
      {name}
    </Link>
  )
}

export function ClaimCard({ claim, currentEntityId }: ClaimCardProps) {
  // ClaimResult.evidence is declared on the backend model but the claims route never
  // populates it — it is always []. The underlying (:Claim)-[:SUPPORTED_BY]->(:Evidence)
  // relationships DO exist for all 5,586 claims; the Cypher simply doesn't traverse them.
  // Fixing that is a backend change (CLAUDE.md §5), so this handles the empty case honestly
  // rather than claiming the evidence doesn't exist. See types/entity.ts.
  const evidenceId = claim.evidence.find((e) => e.evidence_id)?.evidence_id ?? null

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-2.5 flex flex-wrap items-center gap-2">
        <span
          className={cn(
            'inline-flex w-fit items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
            claimTypeColor(claim.claim_type),
          )}
        >
          {claimTypeLabel(claim.claim_type)}
        </span>
        <span
          className={cn(
            'inline-flex w-fit items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
            claimStatusColor(claim.status),
          )}
        >
          {claimStatusLabel(claim.status)}
        </span>
      </div>

      <div className="mb-3 flex items-center gap-2 text-sm">
        <EntityRef id={claim.subject_id} name={claim.subject_name} isCurrent={claim.subject_id === currentEntityId} />
        <ArrowRight className="size-4 shrink-0 text-muted-foreground" />
        <EntityRef id={claim.object_id} name={claim.object_name} isCurrent={claim.object_id === currentEntityId} />
      </div>

      <div className="mb-3 grid grid-cols-2 gap-3 text-xs text-muted-foreground sm:grid-cols-4">
        <div>
          <p className="mb-1">Confidence</p>
          <div className="flex items-center gap-1.5">
            <div className="h-1.5 w-12 rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${Math.round(claim.confidence * 100)}%` }}
              />
            </div>
            <span>{Math.round(claim.confidence * 100)}%</span>
          </div>
        </div>
        <div>
          <p className="mb-1">Valid from</p>
          <p className="text-foreground">{claim.valid_from ?? 'Unknown'}</p>
        </div>
        <div>
          <p className="mb-1">Valid to</p>
          <p className="text-foreground">{claim.valid_to ?? 'Present'}</p>
        </div>
        <div>
          <p className="mb-1">Mentions</p>
          <p className="text-foreground">{claim.mention_count}</p>
        </div>
      </div>

      {evidenceId ? (
        <Link
          to={`/evidence/${encodeURIComponent(evidenceId)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs font-medium text-primary hover:underline"
        >
          View evidence &rarr;
        </Link>
      ) : (
        <p className="text-xs text-muted-foreground italic">
          Evidence links are not returned by this endpoint yet.
        </p>
      )}
    </div>
  )
}
