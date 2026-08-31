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
import type { CitationItem } from '@/types/chat'

interface EvidenceDrawerProps {
  citation: CitationItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function EvidenceDrawer({ citation, open, onOpenChange }: EvidenceDrawerProps) {
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
              {citation.message_subject || citation.message_date ? (
                <div className="rounded-lg bg-muted px-3 py-2">
                  <p className="text-sm font-medium text-foreground">
                    {citation.message_subject || 'Untitled message'}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {citation.message_date ?? 'Date unknown'}
                  </p>
                </div>
              ) : (
                <p className="rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground italic">
                  No source message metadata available for this citation.
                </p>
              )}
            </div>

            <Link
              to={`/evidence/${citation.evidence_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-primary hover:underline"
            >
              View full evidence &rarr;
            </Link>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
