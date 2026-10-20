import { useQuery } from '@tanstack/react-query'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { getHealth } from '@/services/health'

export function DashboardPage() {
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth })

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <Card className="max-w-sm">
        <CardHeader>
          <CardTitle>Estado da API</CardTitle>
          <CardDescription>Ligação ao backend VCCTeamForge</CardDescription>
        </CardHeader>
        <CardContent>
          {health.isPending && <p>A verificar…</p>}
          {health.isError && <p className="text-destructive">API indisponível</p>}
          {health.isSuccess && (
            <p>
              {health.data.status === 'ok' ? 'Operacional' : 'Com problemas'} · v
              {health.data.version}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
