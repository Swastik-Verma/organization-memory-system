interface EvidenceQuoteProps {
  quote: string
}

export function EvidenceQuote({ quote }: EvidenceQuoteProps) {
  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <p className="mb-2 text-xs font-medium text-muted-foreground">Extracted Evidence</p>
      {quote ? (
        <blockquote className="rounded-lg border-l-4 border-primary bg-accent/50 px-4 py-3 text-base italic text-foreground">
          "{quote}"
        </blockquote>
      ) : (
        <p className="rounded-lg bg-muted px-4 py-3 text-sm italic text-muted-foreground">
          No specific quote was extracted for this evidence. See the full email below.
        </p>
      )}
    </section>
  )
}
