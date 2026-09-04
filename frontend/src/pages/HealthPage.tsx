import { useEffect, useState } from 'react'
import { BadgeCheck, FileText, Gauge, Mail, Percent, RefreshCw, Users } from 'lucide-react'
import { ApiErrorState } from '@/components/ApiErrorState'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { StatCard } from '@/components/health/StatCard'
import { ConfidenceDistributionChart } from '@/components/health/ConfidenceDistributionChart'
import { ClaimsByTypeChart } from '@/components/health/ClaimsByTypeChart'
import { ServiceStatusCard } from '@/components/health/ServiceStatusCard'
import { AttentionNeededCard } from '@/components/health/AttentionNeededCard'
import { ClaimsByStatusCard } from '@/components/health/ClaimsByStatusCard'
import { TopEntitiesTable } from '@/components/health/TopEntitiesTable'
import { formatCount, formatPercent, scoreColorClass } from '@/components/health/formatters'
import { fetchHealth, fetchReviewQueue, isAbort } from '@/lib/api'
import type { HealthResponse } from '@/types/health'

// Fetches once on load (plus a manual Refresh button) — deliberately no polling/auto-refresh.
// full_health_report() runs several live aggregation queries across the whole graph; on this
// frozen corpus the numbers never change between requests, so an interval would only add
// real query load for no benefit. See CLAUDE.md-adjacent Day 42 brief, Step 4.

function ReportUnavailableNote() {
  return (
    <p className="text-sm text-muted-foreground">
      Detailed metrics unavailable — the full health report failed to generate on the backend.
    </p>
  )
}

export function HealthPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [reviewTotal, setReviewTotal] = useState<number | null>(null)
  const [fetchedAt, setFetchedAt] = useState<Date | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setHealth(null)
    setError(null)
    setReviewTotal(null)
    setFetchedAt(null)

    fetchHealth({ signal: controller.signal })
      .then((res) => {
        setHealth(res)
        setFetchedAt(new Date())
      })
      .catch((err: unknown) => {
        if (!isAbort(err)) setError(err)
      })

    // Best-effort: the review-queue count degrades to "—" on failure rather than blocking
    // the whole dashboard, since every other card is driven entirely by /api/health.
    fetchReviewQueue({ signal: controller.signal })
      .then((res) => setReviewTotal(res.total))
      .catch(() => {})

    return () => controller.abort()
  }, [reloadToken])

  const report = health?.report ?? null

  const lastUpdatedLabel = report?.timestamp
    ? new Date(report.timestamp).toLocaleString()
    : fetchedAt
      ? fetchedAt.toLocaleString()
      : null

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1.5">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">System Health</h1>
          <p className="text-sm text-muted-foreground">
            Knowledge graph quality metrics and service status
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdatedLabel && (
            <p className="text-xs text-muted-foreground">Last updated: {lastUpdatedLabel}</p>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setReloadToken((n) => n + 1)}
          >
            <RefreshCw className="size-3.5" />
            Refresh
          </Button>
        </div>
      </div>

      {error ? (
        <ApiErrorState error={error} onRetry={() => setReloadToken((n) => n + 1)} />
      ) : !health ? (
        <div className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-5">
            <Skeleton className="h-96 w-full lg:col-span-3" />
            <Skeleton className="h-96 w-full lg:col-span-2" />
          </div>
        </div>
      ) : (
        <>
          {/* Summary stat cards */}
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {report ? (
              <>
                <StatCard
                  icon={Mail}
                  value={formatCount(report.graph_size.nodes.Message ?? 0)}
                  label="Emails Processed"
                />
                <StatCard
                  icon={Users}
                  value={formatCount(
                    (report.graph_size.nodes.Person ?? 0) +
                      (report.graph_size.nodes.Organization ?? 0) +
                      (report.graph_size.nodes.Deal ?? 0),
                  )}
                  label="Total Entities"
                />
                <StatCard
                  icon={FileText}
                  value={formatCount(report.graph_size.nodes.Claim ?? 0)}
                  label="Total Claims"
                />
                <StatCard
                  icon={Gauge}
                  value={`${report.data_quality.quality_score.toFixed(1)} / 100`}
                  label="Quality Score"
                  valueClassName={scoreColorClass(report.data_quality.quality_score)}
                />
                <StatCard
                  icon={Percent}
                  value={formatPercent(report.claim_quality.average_confidence * 100)}
                  label="Avg Confidence"
                />
                <StatCard
                  icon={BadgeCheck}
                  value={formatPercent(report.claim_quality.evidence_verification.verification_rate)}
                  label="Evidence Verified"
                />
              </>
            ) : (
              <div className="col-span-full">
                <ReportUnavailableNote />
              </div>
            )}
          </div>

          {/* Two-column section */}
          <div className="grid gap-4 lg:grid-cols-5">
            <div className="space-y-4 lg:col-span-3">
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="mb-3 text-xs font-medium text-muted-foreground">
                  Confidence Distribution
                </p>
                {report ? (
                  <ConfidenceDistributionChart
                    distribution={report.claim_quality.confidence_distribution}
                  />
                ) : (
                  <ReportUnavailableNote />
                )}
              </div>
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="mb-3 text-xs font-medium text-muted-foreground">Claims by Type</p>
                {report ? (
                  <ClaimsByTypeChart claimsByType={report.claim_quality.claims_by_type} />
                ) : (
                  <ReportUnavailableNote />
                )}
              </div>
            </div>

            <div className="space-y-4 lg:col-span-2">
              <ServiceStatusCard services={health.services} />
              {report ? (
                <AttentionNeededCard
                  pendingReview={reviewTotal}
                  conflictPairs={report.temporal_health.conflict_pairs}
                />
              ) : (
                <div className="rounded-lg border border-border bg-card p-4">
                  <p className="mb-3 text-xs font-medium text-muted-foreground">
                    Attention Needed
                  </p>
                  <ReportUnavailableNote />
                </div>
              )}
              {report ? (
                <ClaimsByStatusCard claimsByStatus={report.temporal_health.claims_by_status} />
              ) : (
                <div className="rounded-lg border border-border bg-card p-4">
                  <p className="mb-3 text-xs font-medium text-muted-foreground">
                    Claims by Status
                  </p>
                  <ReportUnavailableNote />
                </div>
              )}
            </div>
          </div>

          {/* Bottom section */}
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="mb-3 text-xs font-medium text-muted-foreground">
              Top Mentioned Entities
            </p>
            {report ? (
              <TopEntitiesTable topPersons={report.entity_stats.top_persons} />
            ) : (
              <ReportUnavailableNote />
            )}
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
