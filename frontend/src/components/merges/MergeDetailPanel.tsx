// Expandable snapshot comparison for a fuzzy merge row (Day 46). Fetched lazily by
// MergeTable on row expand and cached there — this component is purely presentational.

import { AlertCircle, Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { MergeSnapshot } from '@/types/merge'

export type DetailStatus = 'loading' | 'error' | 'success'

interface MergeDetailPanelProps {
  status: DetailStatus
  sourceSnapshot?: MergeSnapshot
  targetSnapshot?: MergeSnapshot
  errorMessage?: string
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className="break-words text-right text-foreground">{value}</span>
    </div>
  )
}

function SnapshotCard({ title, snapshot }: { title: string; snapshot: MergeSnapshot }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <Field label="Name" value={snapshot.canonical_name} />
        <Field label="Aliases" value={snapshot.aliases.length ? snapshot.aliases.join(', ') : '—'} />
        <Field label="Emails" value={snapshot.emails.length ? snapshot.emails.join(', ') : '—'} />
        <Field label="Mentions" value={snapshot.mention_count.toLocaleString()} />
        <Field
          label="Type"
          value={snapshot.org_type ? `${snapshot.entity_type} (${snapshot.org_type})` : snapshot.entity_type}
        />
      </CardContent>
    </Card>
  )
}

export function MergeDetailPanel({
  status,
  sourceSnapshot,
  targetSnapshot,
  errorMessage,
}: MergeDetailPanelProps) {
  if (status === 'loading') {
    return (
      <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        Loading merge details…
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="my-2 flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        <AlertCircle className="size-4 shrink-0" />
        {errorMessage ?? 'Failed to load merge details.'}
      </div>
    )
  }

  if (!sourceSnapshot || !targetSnapshot) return null

  return (
    <div className="grid grid-cols-1 gap-3 py-3 sm:grid-cols-2">
      <SnapshotCard title="Source Entity (absorbed)" snapshot={sourceSnapshot} />
      <SnapshotCard title="Target Entity (survived)" snapshot={targetSnapshot} />
    </div>
  )
}
