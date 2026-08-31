import type { CitationItem } from '@/types/chat'

interface CitationBadgeProps {
  citation: CitationItem
  onClick: (citation: CitationItem) => void
}

export function CitationBadge({ citation, onClick }: CitationBadgeProps) {
  return (
    <button
      type="button"
      onClick={() => onClick(citation)}
      className="mx-0.5 inline-flex h-4 min-w-4 -translate-y-0.5 items-center justify-center rounded-full bg-accent px-1 text-[0.65rem] font-semibold text-accent-foreground align-super transition-colors hover:bg-primary hover:text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
      aria-label={`View evidence for citation ${citation.index}`}
    >
      {citation.index}
    </button>
  )
}
