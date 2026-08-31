import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'
import { claimTypeColor, claimTypeLabel } from '@/lib/claimTypes'
import { mockFetchEntityTimeline } from '@/mocks/entityMocks'
import type { TimelineEvent } from '@/types/entity'

interface TimelineTabProps {
  entityId: string
}

export function TimelineTab({ entityId }: TimelineTabProps) {
  const [events, setEvents] = useState<TimelineEvent[] | null>(null)

  useEffect(() => {
    let cancelled = false
    setEvents(null)
    mockFetchEntityTimeline(entityId).then((res) => {
      if (!cancelled) setEvents(res.events)
    })
    return () => {
      cancelled = true
    }
  }, [entityId])

  if (events === null) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    )
  }

  if (events.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
        No timeline events for this entity yet.
      </p>
    )
  }

  return (
    <div className="relative space-y-6 border-l border-border pl-6">
      {events.map((event) => (
        <div key={event.claim_id} className="relative">
          <span className="absolute top-1 -left-[1.6rem] size-2.5 rounded-full border-2 border-background bg-primary" />
          <p className="text-xs font-medium text-muted-foreground">{event.valid_from ?? 'Date unknown'}</p>
          <p className="mt-0.5 text-sm text-foreground">{event.description}</p>
          <div className="mt-1.5 flex items-center gap-2">
            <span
              className={cn(
                'inline-flex w-fit items-center rounded-full px-2 py-0.5 text-[0.7rem] font-medium',
                claimTypeColor(event.claim_type),
              )}
            >
              {claimTypeLabel(event.claim_type)}
            </span>
            <span className="text-xs text-muted-foreground">{Math.round(event.confidence * 100)}% confidence</span>
          </div>
        </div>
      ))}
    </div>
  )
}
