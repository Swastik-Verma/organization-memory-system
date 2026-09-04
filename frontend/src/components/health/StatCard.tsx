import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface StatCardProps {
  icon: LucideIcon
  value: string
  label: string
  /** Overrides the default foreground color on the value, e.g. for the quality-score traffic light. */
  valueClassName?: string
}

export function StatCard({ icon: Icon, value, label, valueClassName }: StatCardProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <Icon className="size-4 text-muted-foreground" />
      <p className={cn('mt-2 text-2xl font-semibold tabular-nums text-foreground', valueClassName)}>
        {value}
      </p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  )
}
