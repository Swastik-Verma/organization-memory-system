// Small shared formatters for the Day 42 health dashboard — kept separate from any one
// component since stat cards, charts and tables all need consistent number formatting.

export function formatCount(n: number): string {
  return n.toLocaleString()
}

export function formatPercent(n: number, digits = 1): string {
  return `${n.toFixed(digits)}%`
}

/** quality_score / average_confidence-style thresholds shared by any "traffic light" stat. */
export function scoreColorClass(score: number): string {
  if (score >= 95) return 'text-emerald-600'
  if (score >= 85) return 'text-amber-600'
  return 'text-red-600'
}
