import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { formatNumber } from '@/features/analytics/format'
import type { TrendPoint } from '@/services/analytics'
import { formatDate } from '@/services/common'
import { issueStatusLabels } from '@/services/issues'
import type { StatusBreakdown, VelocityEntry } from '@/services/reports'

const CHART_HEIGHT = 260
const CHART_INITIAL_SIZE = { width: 600, height: CHART_HEIGHT }
const MARGIN = { top: 8, right: 16, bottom: 8, left: 0 }
const BAR_RADIUS: [number, number, number, number] = [4, 4, 0, 0]

function tooltipNumber(value: unknown) {
  return formatNumber(typeof value === 'number' ? value : null)
}

export function TrendChart({ points }: { points: TrendPoint[] }) {
  if (points.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Ainda não há snapshots diários para mostrar tendências.
      </p>
    )
  }
  const data = points.map((point) => ({ ...point, label: formatDate(point.day).slice(0, 5) }))
  return (
    <div className="h-[260px] w-full" aria-label="Gráfico de tendências" role="img">
      <ResponsiveContainer width="100%" height={CHART_HEIGHT} initialDimension={CHART_INITIAL_SIZE}>
        <LineChart data={data} margin={MARGIN}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis dataKey="label" />
          <YAxis allowDecimals={false} />
          <Tooltip formatter={tooltipNumber} />
          <Legend />
          <Line name="Abertas" dataKey="openCount" stroke="var(--chart-1)" strokeWidth={2} />
          <Line name="Em progresso" dataKey="inProgressCount" stroke="var(--chart-2)" />
          <Line name="Bloqueadas" dataKey="blockedCount" stroke="var(--destructive)" />
          <Line name="Concluídas" dataKey="doneCount" stroke="var(--chart-3)" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export function StatusChart({ breakdown }: { breakdown: StatusBreakdown[] }) {
  const data = breakdown.map((item) => ({ ...item, label: issueStatusLabels[item.status] }))
  return (
    <div className="h-[260px] w-full" aria-label="Gráfico de distribuição por estado" role="img">
      <ResponsiveContainer width="100%" height={CHART_HEIGHT} initialDimension={CHART_INITIAL_SIZE}>
        <BarChart data={data} margin={MARGIN}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis dataKey="label" />
          <YAxis allowDecimals={false} />
          <Tooltip formatter={tooltipNumber} />
          <Bar name="Issues" dataKey="issueCount" fill="var(--chart-1)" radius={BAR_RADIUS} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function VelocityChart({ entries }: { entries: VelocityEntry[] }) {
  return (
    <div className="h-[260px] w-full" aria-label="Gráfico de velocidade" role="img">
      <ResponsiveContainer width="100%" height={CHART_HEIGHT} initialDimension={CHART_INITIAL_SIZE}>
        <BarChart data={entries} margin={MARGIN}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis dataKey="name" />
          <YAxis allowDecimals={false} />
          <Tooltip formatter={tooltipNumber} />
          <Legend />
          <Bar
            name="Compromisso"
            dataKey="committedStoryPoints"
            fill="var(--chart-2)"
            radius={BAR_RADIUS}
          />
          <Bar
            name="Concluído"
            dataKey="completedStoryPoints"
            fill="var(--chart-1)"
            radius={BAR_RADIUS}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Gráficos do dashboard geral (exportação por omissão para `React.lazy`). */
export default function DashboardCharts({
  breakdown,
  trend,
}: {
  breakdown: StatusBreakdown[]
  trend: TrendPoint[]
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="space-y-2">
        <h3 className="text-lg font-semibold">Distribuição por estado</h3>
        <StatusChart breakdown={breakdown} />
      </section>
      <section className="space-y-2">
        <h3 className="text-lg font-semibold">Tendências (30 dias)</h3>
        <TrendChart points={trend} />
      </section>
    </div>
  )
}
