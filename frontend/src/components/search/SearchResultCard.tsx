import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { entityTypeBadgeClass, entityTypeLabel } from '@/lib/entityTypes'
import { claimTypeColor, claimTypeLabel } from '@/lib/claimTypes'
import { confidenceBarClass, confidenceLevelClass, extractClaimType } from '@/lib/searchTypes'
import { highlightMatch } from '@/lib/highlightMatch'
import type { SearchResultItem } from '@/types/search'

interface SearchResultCardProps {
  item: SearchResultItem
  query: string
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100)
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1.5 w-10 rounded-full bg-muted">
        <div className={cn('h-full rounded-full', confidenceBarClass(confidence))} style={{ width: `${pct}%` }} />
      </div>
      <span className={cn('rounded px-1.5 py-0.5 text-xs font-medium', confidenceLevelClass(confidence))}>
        {pct}%
      </span>
    </div>
  )
}

function CardShell({ children, to, external }: { children: ReactNode; to?: string; external?: boolean }) {
  if (!to) {
    return <Card size="sm">{children}</Card>
  }
  return (
    <Link
      to={to}
      target={external ? '_blank' : undefined}
      rel={external ? 'noopener noreferrer' : undefined}
      className="block"
    >
      <Card size="sm" className="transition-colors hover:bg-accent/50">
        {children}
      </Card>
    </Link>
  )
}

function PersonOrgCard({ item, query }: SearchResultCardProps) {
  return (
    <CardShell to={`/entities/${encodeURIComponent(item.id)}`} external>
      <CardContent className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span
            className={cn(
              'inline-flex w-fit shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium',
              entityTypeBadgeClass(item.type),
            )}
          >
            {entityTypeLabel(item.type)}
          </span>
          <span className="truncate text-sm font-medium text-foreground">{highlightMatch(item.name, query)}</span>
        </div>
        <span className="shrink-0 text-xs text-muted-foreground">
          {item.mention_count.toLocaleString()} mentions
        </span>
      </CardContent>
    </CardShell>
  )
}

// SearchResultItem still has no claim_type/object_id (see types/search.ts header comment),
// so claim_type is recovered best-effort via extractClaimType(). subject_id was added to the
// backend response after the initial build, so the card now links to the subject's entity
// page when present — defensively falls back to plain (non-clickable) text if it's ever null.
function ClaimCard({ item, query }: SearchResultCardProps) {
  const claimType = extractClaimType(item.name)
  const body = (
    <CardContent className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {claimType && (
          <span
            className={cn(
              'inline-flex w-fit items-center rounded-full px-2 py-0.5 text-xs font-medium',
              claimTypeColor(claimType),
            )}
          >
            {claimTypeLabel(claimType)}
          </span>
        )}
        {item.date && <span className="text-xs text-muted-foreground">{item.date}</span>}
      </div>
      <p className="text-sm text-foreground">{highlightMatch(item.name, query)}</p>
      {item.confidence !== null && <ConfidenceBadge confidence={item.confidence} />}
    </CardContent>
  )
  if (!item.subject_id) {
    return <CardShell>{body}</CardShell>
  }
  return (
    <CardShell to={`/entities/${encodeURIComponent(item.subject_id)}`} external>
      {body}
    </CardShell>
  )
}

function EvidenceCard({ item, query }: SearchResultCardProps) {
  return (
    <CardShell to={`/evidence/${encodeURIComponent(item.id)}`} external>
      <CardContent className="space-y-2">
        <p className="text-sm italic text-foreground">"{highlightMatch(item.snippet, query)}"</p>
        <div className="flex flex-wrap items-center gap-3">
          {item.confidence !== null && <ConfidenceBadge confidence={item.confidence} />}
          {item.date && <span className="text-xs text-muted-foreground">{item.date}</span>}
        </div>
      </CardContent>
    </CardShell>
  )
}

// Deal/Decision have no dedicated detail page (see CLAUDE.md §8.7 endpoint table) — link into
// the Graph Explorer instead, matching the entity detail page's own "View in Graph Explorer"
// pattern. Uses `?entity=`, the param GraphExplorerPage actually reads (confirmed in
// src/pages/GraphExplorerPage.tsx) — the day brief's `?node=` example does not match what Day
// 41 built.
function DealDecisionCard({ item, query }: SearchResultCardProps) {
  return (
    <CardShell to={`/graph?entity=${encodeURIComponent(item.id)}`}>
      <CardContent>
        <p className="text-sm font-medium text-foreground">{highlightMatch(item.name, query)}</p>
      </CardContent>
    </CardShell>
  )
}

export function SearchResultCard({ item, query }: SearchResultCardProps) {
  switch (item.type) {
    case 'person':
    case 'organization':
      return <PersonOrgCard item={item} query={query} />
    case 'claim':
      return <ClaimCard item={item} query={query} />
    case 'evidence':
      return <EvidenceCard item={item} query={query} />
    case 'deal':
    case 'decision':
      return <DealDecisionCard item={item} query={query} />
  }
}
