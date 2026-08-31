import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import { EntityTypeBadge } from '@/components/entity/EntityTypeBadge'
import type { EntityDetailResponse } from '@/types/entity'

interface EntityHeaderProps {
  entity: EntityDetailResponse
}

export function EntityHeader({ entity }: EntityHeaderProps) {
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
          <span>{entity.mention_count} mentions</span>
          <span>{entity.claim_count} claims</span>
          <span>
            First seen {entity.first_seen ?? 'unknown'} &middot; Last seen {entity.last_seen ?? 'unknown'}
          </span>
        </div>
      </div>
    </div>
  )
}
