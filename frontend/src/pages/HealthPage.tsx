import { useEffect, useState } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'
import { ApiErrorState } from '@/components/ApiErrorState'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { fetchHealth, isAbort } from '@/lib/api'
import type { HealthResponse } from '@/types/health'

// Basic version only — the full health dashboard is Day 42. This shows service status and
// the raw node/edge counts the endpoint already returns; charts, history and the
// conflicts/review-queue surfaces come later.

const COUNT_ORDER = [
  'Person',
  'Organization',
  'Deal',
  'Decision',
  'Claim',
  'Evidence',
  'Message',
  'total_edges',
  'vectors',
]

const COUNT_LABELS: Record<string, string> = {
  total_edges: 'Edges',
  vectors: 'Qdrant vectors',
}

function countLabel(key: string): string {
  return COUNT_LABELS[key] ?? key
}

export function HealthPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setHealth(null)
    setError(null)
    fetchHealth({ signal: controller.signal })
      .then(setHealth)
      .catch((err: unknown) => {
        if (!isAbort(err)) setError(err)
      })
    return () => controller.abort()
  }, [reloadToken])

  // Any key the backend returns that isn't in COUNT_ORDER still gets rendered — `counts` is
  // built dynamically from whatever labels exist in the graph, so a hard-coded list alone
  // would silently hide a new node type.
  const countKeys = health
    ? [
        ...COUNT_ORDER.filter((k) => k in health.counts),
        ...Object.keys(health.counts).filter((k) => !COUNT_ORDER.includes(k)),
      ]
    : []

  return (
    <div className="space-y-6">
      <div className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Health</h1>
        <p className="text-sm text-muted-foreground">Backend service status and graph size</p>
      </div>

      {error ? (
        <ApiErrorState error={error} onRetry={() => setReloadToken((n) => n + 1)} />
      ) : !health ? (
        <div className="space-y-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            {health.services.map((service) => {
              const ok = service.status === 'ok'
              return (
                <div key={service.name} className="rounded-lg border border-border bg-card p-4">
                  <div className="flex items-center gap-2">
                    {ok ? (
                      <CheckCircle2 className="size-4 text-emerald-600" />
                    ) : (
                      <XCircle className="size-4 text-destructive" />
                    )}
                    <span className="text-sm font-medium text-foreground capitalize">
                      {service.name}
                    </span>
                    <span
                      className={cn(
                        'ml-auto rounded-full px-2 py-0.5 text-xs font-medium',
                        ok ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700',
                      )}
                    >
                      {ok ? 'Connected' : 'Error'}
                    </span>
                  </div>
                  {service.detail && (
                    <p className="mt-1.5 text-xs text-muted-foreground">{service.detail}</p>
                  )}
                </div>
              )
            })}
          </div>

          <div className="rounded-lg border border-border bg-card p-4">
            <p className="mb-3 text-xs font-medium text-muted-foreground">Graph contents</p>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
              {countKeys.map((key) => (
                <div key={key}>
                  <p className="text-xl font-semibold tabular-nums text-foreground">
                    {health.counts[key].toLocaleString()}
                  </p>
                  <p className="text-xs text-muted-foreground">{countLabel(key)}</p>
                </div>
              ))}
            </div>
          </div>

          <p className="text-xs text-muted-foreground">
            Overall status:{' '}
            <span className="font-medium text-foreground capitalize">{health.status}</span>
          </p>
        </>
      )}
    </div>
  )
}
