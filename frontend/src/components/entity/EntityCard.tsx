import { Link } from 'react-router-dom'
import { EntityTypeBadge } from '@/components/entity/EntityTypeBadge'
import type { EntityListItem } from '@/types/entity'

interface EntityCardProps {
  entity: EntityListItem
}

export function EntityCard({ entity }: EntityCardProps) {
  return (
    <Link
      to={`/entities/${encodeURIComponent(entity.id)}`}
      className="flex items-center justify-between gap-4 rounded-lg border border-border bg-card px-4 py-3 transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
    >
      <div className="flex min-w-0 items-center gap-3">
        <EntityTypeBadge type={entity.type} />
        <span className="truncate text-sm font-medium text-foreground">{entity.name}</span>
      </div>
      <div className="flex shrink-0 items-center gap-4 text-xs text-muted-foreground">
        <span>{entity.mention_count} mentions</span>
        <span>{entity.claim_count} claims</span>
      </div>
    </Link>
  )
}
