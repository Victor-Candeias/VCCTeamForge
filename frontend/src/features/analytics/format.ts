export function formatNumber(value: number | null) {
  return value === null ? '—' : value.toLocaleString('pt-PT', { maximumFractionDigits: 1 })
}

export function formatPercent(value: number | null) {
  return value === null ? '—' : `${formatNumber(value)}%`
}

/** Taxas devolvidas como fração (0–1). */
export function formatRate(value: number | null) {
  return value === null ? '—' : formatPercent(value * 100)
}

export function formatDays(value: number | null) {
  return value === null ? '—' : `${formatNumber(value)} d`
}
