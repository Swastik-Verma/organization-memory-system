import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

interface ConfidenceDistributionChartProps {
  distribution: Record<string, number>
}

const INDIGO = '#4f46e5'

/** Sorts whatever bucket keys are actually present ("0.90-1.00", "0.70-0.89", ...) descending
 * by their lower bound — the backend omits empty buckets entirely rather than sending them
 * with a 0 count, so this must never assume all 5 possible buckets exist. */
export function sortedBuckets(distribution: Record<string, number>) {
  return Object.entries(distribution)
    .map(([bucket, count]) => ({ bucket, count }))
    .sort((a, b) => parseFloat(b.bucket) - parseFloat(a.bucket))
}

export function ConfidenceDistributionChart({ distribution }: ConfidenceDistributionChartProps) {
  const data = sortedBuckets(distribution)

  if (data.length === 0) {
    return <p className="text-sm text-muted-foreground">No confidence data available.</p>
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey="bucket"
          tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }}
          axisLine={{ stroke: 'var(--border)' }}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
        />
        <Tooltip
          formatter={(value) => [Number(value).toLocaleString(), 'Claims']}
          contentStyle={{
            borderRadius: 8,
            borderColor: 'var(--border)',
            fontSize: 12,
          }}
        />
        <Bar dataKey="count" fill={INDIGO} radius={[6, 6, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
