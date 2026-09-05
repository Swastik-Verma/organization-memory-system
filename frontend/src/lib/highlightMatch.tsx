import type { ReactNode } from 'react'

/**
 * Wraps the first case-insensitive occurrence of `query` inside `text` in a <mark>. Nice-to-
 * have per the Day 45 brief ("skip if complex") — kept deliberately simple: first match only,
 * no multi-term splitting, plain substring search (no regex-special-char escaping needed
 * since it never becomes a RegExp).
 */
export function highlightMatch(text: string, query: string): ReactNode {
  const trimmed = query.trim()
  if (!trimmed) return text

  const index = text.toLowerCase().indexOf(trimmed.toLowerCase())
  if (index === -1) return text

  const before = text.slice(0, index)
  const match = text.slice(index, index + trimmed.length)
  const after = text.slice(index + trimmed.length)

  return (
    <>
      {before}
      <mark className="rounded-sm bg-yellow-200 px-0.5 text-foreground">{match}</mark>
      {after}
    </>
  )
}
