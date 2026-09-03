import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import { EntityTypeBadge } from '@/components/entity/EntityTypeBadge'
import type { EntityDetailResponse, EntityStats } from '@/types/entity'

interface EntityHeaderProps {
  entity: EntityDetailResponse
  /** Claim count and first/last-seen dates. The real EntityDetailResponse carries none of
   *  these, so EntityDetailPage derives them from the entity's claims and passes them in.
   *  null while that second request is still in flight. */
  stats: EntityStats | null
}

export function EntityHeader({ entity, stats }: EntityHeaderProps) {
  return (
    <div className="space-y-4">
      <Link
        to="/entities"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Back to Entities
      </Link>

      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">{entity.name}</h1>
          <EntityTypeBadge type={entity.type} />
        </div>

        {entity.aliases.length > 0 && (
          <p className="text-sm text-muted-foreground">Also known as: {entity.aliases.join(', ')}</p>
        )}

        <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
          <span>{entity.mention_count.toLocaleString()} mentions</span>
          <span>{stats ? `${stats.claim_count.toLocaleString()} claims` : 'Counting claims…'}</span>
          {stats && (stats.first_seen || stats.last_seen) && (
            <span>
              First seen {stats.first_seen ?? 'unknown'} &middot; Last seen{' '}
              {stats.last_seen ?? 'unknown'}
            </span>
          )}
        </div>

        {entity.emails.length > 0 && (
          <p className="text-sm text-muted-foreground">{entity.emails.join(', ')}</p>
        )}
      </div>
    </div>
  )
}
