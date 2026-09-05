import { cn } from '@/lib/utils'

/** Small colored pill badge, shared by ConflictCard.tsx and AutoResolvedCard.tsx (both need
 *  identical classification/resolution/status pills). */
export function Pill({ className, children }: { className: string; children: React.ReactNode }) {
  return (
    <span className={cn('inline-flex w-fit items-center rounded-full px-2.5 py-0.5 text-xs font-medium', className)}>
      {children}
    </span>
  )
}

/** Parses a "YYYY-MM-DD" date-only string as LOCAL calendar date components rather than
 *  `new Date(str)` (which parses date-only ISO strings as UTC midnight — under a negative UTC
 *  offset that renders as the previous day once toLocaleDateString formats it in local time).
 *  Extracted here (rather than duplicated per card) specifically because this timezone
 *  subtlety is easy to silently lose if re-typed in a second file. */
export function formatConflictDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}
