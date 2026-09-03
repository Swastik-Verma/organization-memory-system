import type { EvidenceDetailResponse } from '@/types/evidence'

interface SourceEmailProps {
  evidence: EvidenceDetailResponse
}

/** Renders email_body, highlighting the evidence_quote inline when it appears verbatim in
 * the body (simple `includes` string match per the Day 40 brief — no char-offset math). */
function renderBody(body: string, quote: string) {
  if (!quote || !body.includes(quote)) {
    return body
  }
  const parts = body.split(quote)
  return parts.map((part, i) => (
    <span key={i}>
      {part}
      {i < parts.length - 1 && (
        <mark className="rounded-sm bg-amber-200/70 px-0.5 text-foreground">{quote}</mark>
      )}
    </span>
  ))
}

export function SourceEmail({ evidence }: SourceEmailProps) {
  // No "To" row: EvidenceDetailResponse carries only email_from, with no recipient list.
  const { email_from, email_date, email_subject, email_body, quote } = evidence

  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <p className="mb-3 text-xs font-medium text-muted-foreground">Source Email</p>

      <div className="mb-3 space-y-1 rounded-lg border border-border bg-muted/40 px-4 py-3 text-xs">
        <div className="flex gap-2">
          <span className="w-14 shrink-0 text-muted-foreground">From</span>
          <span className="text-foreground">{email_from ?? 'Unknown sender'}</span>
        </div>
        <div className="flex gap-2">
          <span className="w-14 shrink-0 text-muted-foreground">Date</span>
          <span className="text-foreground">{email_date ?? 'Unknown'}</span>
        </div>
        <div className="flex gap-2">
          <span className="w-14 shrink-0 text-muted-foreground">Subject</span>
          <span className="text-foreground">{email_subject ?? 'Untitled'}</span>
        </div>
      </div>

      <div className="max-h-[32rem] overflow-y-auto rounded-lg border border-border bg-background px-4 py-3">
        <pre className="whitespace-pre-wrap break-words font-mono text-sm leading-relaxed text-foreground">
          {email_body ? renderBody(email_body, quote) : 'No email body available.'}
        </pre>
      </div>
    </section>
  )
}
