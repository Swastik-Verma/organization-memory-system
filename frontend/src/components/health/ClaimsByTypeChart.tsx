import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { claimTypeLabel } from '@/lib/claimTypes'

interface ClaimsByTypeChartProps {
  claimsByType: Record<string, number>
}

const INDIGO = '#4f46e5'

export function ClaimsByTypeChart({ claimsByType }: ClaimsByTypeChartProps) {
  const data = Object.entries(claimsByType)
    .map(([type, count]) => ({ type: claimTypeLabel(type), count }))
    .sort((a, b) => b.count - a.count)

  if (data.length === 0) {
    return <p className="text-sm text-muted-foreground">No claim-type data available.</p>
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 4, right: 16, left: 8, bottom: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
        <XAxis
          type="number"
          tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }}
          axisLine={{ stroke: 'var(--border)' }}
          tickLine={false}
          allowDecimals={false}
        />
        <YAxis
          type="category"
          dataKey="type"
          width={110}
          tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          formatter={(value) => [Number(value).toLocaleString(), 'Claims']}
          contentStyle={{
            borderRadius: 8,
            borderColor: 'var(--border)',
            fontSize: 12,
          }}
        />
        <Bar dataKey="count" fill={INDIGO} radius={[0, 6, 6, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
