import { useEffect, useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import { claimTypeColor, claimTypeLabel } from '@/lib/claimTypes'
import { fetchEvidence, isAbort } from '@/lib/api'
import type { CitationItem } from '@/types/chat'
import type { EvidenceDetailResponse } from '@/types/evidence'

interface EvidenceDrawerProps {
  citation: CitationItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

type SourceState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'loaded'; evidence: EvidenceDetailResponse }
  | { status: 'error' }

/**
 * The "Source" section's subject line and date.
 *
 * Day 37 read these off CitationItem.message_subject / message_date, which were mock-only
 * fields — the real CitationItem returned by POST /api/chat has never carried them. They
 * are fetched here instead from GET /api/evidence/{evidence_id}, which does carry
 * email_subject and email_date. That request is quota-free (Neo4j only) and fires only when
 * the drawer actually opens, not for every citation in an answer.
 */
function SourceSection({ state }: { state: SourceState }) {
  if (state.status === 'loading' || state.status === 'idle') {
    return (
      <div className="animate-pulse space-y-1.5 rounded-lg bg-muted px-3 py-2">
        <div className="h-4 w-3/4 rounded bg-muted-foreground/20" />
        <div className="h-3 w-1/3 rounded bg-muted-foreground/20" />
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <p className="rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground italic">
        Source metadata unavailable.
      </p>
    )
  }

  const { email_subject, email_date } = state.evidence
  if (!email_subject && !email_date) {
    return (
      <p className="rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground italic">
        No source message metadata available for this citation.
      </p>
    )
  }

  return (
    <div className="rounded-lg bg-muted px-3 py-2">
      <p className="text-sm font-medium text-foreground">{email_subject || 'Untitled message'}</p>
      <p className="text-xs text-muted-foreground">{email_date ?? 'Date unknown'}</p>
    </div>
  )
}

export function EvidenceDrawer({ citation, open, onOpenChange }: EvidenceDrawerProps) {
  const [source, setSource] = useState<SourceState>({ status: 'idle' })
  const evidenceId = citation?.evidence_id ?? null

  useEffect(() => {
    // Only fetch while the drawer is actually open, so closing it cancels an in-flight
    // request and reopening on a different citation starts a fresh one.
    if (!open || !evidenceId) {
      setSource({ status: 'idle' })
      return
    }
    const controller = new AbortController()
    setSource({ status: 'loading' })
    fetchEvidence(evidenceId, { signal: controller.signal })
      .then((evidence) => setSource({ status: 'loaded', evidence }))
      .catch((err: unknown) => {
        if (!isAbort(err)) setSource({ status: 'error' })
      })
    return () => controller.abort()
  }, [open, evidenceId])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Evidence</SheetTitle>
        </SheetHeader>
        {citation && (
          <div className="flex flex-col gap-4 px-4 pb-4">
            <span
              className={cn(
                'inline-flex w-fit items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
                claimTypeColor(citation.claim_type),
              )}
            >
              {claimTypeLabel(citation.claim_type)}
            </span>

            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <span>{citation.subject_name}</span>
              <ArrowRight className="size-4 shrink-0 text-muted-foreground" />
              <span>{citation.object_name}</span>
            </div>

            <div>
              <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
                <span>Confidence</span>
                <span>{Math.round(citation.confidence * 100)}%</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${Math.round(citation.confidence * 100)}%` }}
                />
              </div>
            </div>

            <div>
              <p className="mb-1.5 text-xs text-muted-foreground">Evidence quote</p>
              {citation.evidence_quote ? (
                <blockquote className="rounded-lg border-l-2 border-primary bg-accent/50 px-3 py-2 text-sm text-foreground italic">
                  "{citation.evidence_quote}"
                </blockquote>
              ) : (
                <p className="rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground italic">
                  No verbatim quote available for this citation.
                </p>
              )}
            </div>

            <div>
              <p className="mb-1.5 text-xs text-muted-foreground">Source</p>
              <SourceSection state={source} />
            </div>

            {citation.evidence_id ? (
              <Link
                to={`/evidence/${encodeURIComponent(citation.evidence_id)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-primary hover:underline"
              >
                View full evidence &rarr;
              </Link>
            ) : (
              <p className="text-sm text-muted-foreground italic">
                This citation has no linked evidence record.
              </p>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
