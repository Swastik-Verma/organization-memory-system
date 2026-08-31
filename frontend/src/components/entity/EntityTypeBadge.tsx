import { cn } from '@/lib/utils'
import { entityTypeBadgeClass, entityTypeLabel } from '@/lib/entityTypes'

interface EntityTypeBadgeProps {
  type: string
  className?: string
}

export function EntityTypeBadge({ type, className }: EntityTypeBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex w-fit items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        entityTypeBadgeClass(type),
        className,
      )}
    >
      {entityTypeLabel(type)}
    </span>
  )
}
