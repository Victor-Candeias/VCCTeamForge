import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { routes } from '@/app/router'
import {
  csrfHandler,
  jsonResponse,
  mockApi,
  renderRoutes,
  testProject,
  testUser,
} from '@/test/utils'

const devUser = {
  ...testUser,
  permissions: ['projects:read', 'issues:read', 'issues:write', 'reports:read'],
}
const leadUser = {
  ...testUser,
  id: 'tl1',
  role: 'tech_lead' as const,
  permissions: [...devUser.permissions, 'projects:manage', 'sprints:manage'],
}
const ana = { id: '1', name: 'Ana', email: 'ana@exemplo.pt', role: 'developer' }

const kpis = {
  openCount: 7,
  inProgressCount: 3,
  blockedCount: 1,
  doneCount: 12,
  criticalBugCount: 2,
  openStoryPoints: 21,
  testPassRate: 0.875,
  testRunCount: 16,
}

const breakdown = [
  { status: 'todo', issueCount: 3, storyPoints: 8 },
  { status: 'in_progress', issueCount: 3, storyPoints: 13 },
  { status: 'code_review', issueCount: 0, storyPoints: 0 },
  { status: 'testing', issueCount: 0, storyPoints: 0 },
  { status: 'done', issueCount: 12, storyPoints: 30 },
]

function issue(overrides: Record<string, unknown> = {}) {
  return {
    id: 'i1',
    key: 'APP-1',
    title: 'Login lento',
    projectId: 'p1',
    type: 'story',
    status: 'in_progress',
    priority: 'high',
    assignee: ana,
    since: '2026-01-01T10:00:00Z',
    ageDays: 5,
    ...overrides,
  }
}

function overview() {
  return {
    projectId: null,
    projectCount: 2,
    kpis,
    statusBreakdown: breakdown,
    activeSprints: [
      {
        sprintId: 's1',
        projectId: 'p1',
        projectKey: 'APP',
        projectName: 'Aplicação',
        name: 'Sprint 4',
        goal: 'Fechar o login',
        startDate: '2026-01-05',
        endDate: '2026-01-18',
        remainingDays: 4,
        issueCount: 6,
        completedIssueCount: 3,
        storyPoints: 20,
        completedStoryPoints: 10,
        progressPercent: 50,
      },
    ],
    alerts: [
      { kind: 'blocked', label: 'Bloqueadas há mais de 3 dias', total: 1, issues: [issue()] },
      { kind: 'stale', label: 'Sem atualização há mais de 14 dias', total: 0, issues: [] },
      {
        kind: 'unassigned_critical_bugs',
        label: 'Bugs críticos sem responsável',
        total: 1,
        issues: [
          issue({
            id: 'i2',
            key: 'APP-2',
            title: 'Crash no arranque',
            type: 'bug',
            priority: 'critical',
            assignee: null,
          }),
        ],
      },
    ],
    myWork: { openCount: 1, inProgressCount: 1, blockedCount: 0, issues: [issue()] },
    trend: [],
    generatedAt: '2026-01-14T10:00:00Z',
  }
}

function metrics(overrides: Record<string, unknown> = {}) {
  return {
    projectId: 'p1',
    filters: { sprintId: null, type: null, from: '2025-10-17', to: '2026-01-14' },
    kpis,
    statusBreakdown: breakdown,
    velocity: {
      sprints: [
        {
          sprintId: 's0',
          name: 'Sprint 3',
          committedStoryPoints: 20,
          completedStoryPoints: 18,
          committedCompletedStoryPoints: 16,
          predictabilityPercent: 80,
        },
      ],
      averageVelocity: 18,
      averagePredictabilityPercent: 80,
    },
    leadTime: { count: 4, averageDays: 6.5, medianDays: 5, p85Days: 10.2 },
    cycleTime: { count: 4, averageDays: 2.5, medianDays: 2, p85Days: 4 },
    aging: {
      buckets: [
        { label: '0–7 dias', minDays: 0, maxDays: 7, count: 4 },
        { label: '8–30 dias', minDays: 8, maxDays: 30, count: 2 },
        { label: '31–90 dias', minDays: 31, maxDays: 90, count: 1 },
        { label: '> 90 dias', minDays: 91, maxDays: null, count: 0 },
      ],
      oldest: [issue({ title: 'Issue antiga', ageDays: 45 })],
    },
    bugSeverity: [
      { priority: 'critical', open: 2, done: 1, total: 3 },
      { priority: 'high', open: 0, done: 0, total: 0 },
      { priority: 'medium', open: 0, done: 0, total: 0 },
      { priority: 'low', open: 0, done: 0, total: 0 },
    ],
    qa: {
      runCount: 16,
      counts: { pass: 14, fail: 2, blocked: 0, not_run: 0, skipped: 0 },
      passRate: 0.875,
    },
    releases: [
      {
        releaseId: 'r1',
        name: '1.4.0',
        status: 'ready_for_qa',
        plannedDate: '2026-02-01',
        releasedAt: null,
        issueCount: 5,
        doneIssueCount: 4,
        knownBugCount: 1,
        openBugCount: 1,
        openCriticalBugCount: 0,
        testPassRate: 1,
        ready: false,
      },
    ],
    workload: [
      { assignee: ana, openCount: 4, inProgressCount: 2, blockedCount: 1, openStoryPoints: 13 },
      { assignee: null, openCount: 3, inProgressCount: 0, blockedCount: 0, openStoryPoints: 8 },
    ],
    trend: [],
    sprints: [{ id: 's0', name: 'Sprint 3', status: 'closed' }],
    generatedAt: '2026-01-14T10:00:00Z',
    ...overrides,
  }
}

function headings() {
  return screen
    .getAllByRole('heading', { level: 3 })
    .map((heading) => heading.textContent)
    .filter((text) => ['Alertas', 'Sprints ativos', 'O meu trabalho'].includes(text ?? ''))
}

describe('Dashboard geral', () => {
  it('mostra KPIs, sprints, alertas e o trabalho do utilizador por perfil', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(devUser),
      'GET /api/health': () => jsonResponse({ status: 'ok', version: '0.1.0' }),
      'GET /api/dashboard/overview': () => jsonResponse(overview()),
    })
    renderRoutes(routes)

    expect(
      await screen.findByText('Visão de equipa: o seu trabalho primeiro.', { exact: false }),
    ).toBeInTheDocument()
    expect(screen.getByText('87,5%')).toBeInTheDocument()
    expect(screen.getByText('Bugs críticos')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'APP · Sprint 4' })).toHaveAttribute(
      'href',
      '/projects/p1/sprints/s1/dashboard',
    )
    expect(screen.getByRole('progressbar', { name: 'Progresso de Sprint 4' })).toHaveAttribute(
      'aria-valuenow',
      '50',
    )
    expect(screen.getByText('Crash no arranque')).toBeInTheDocument()
    expect(headings()).toEqual(['O meu trabalho', 'Sprints ativos', 'Alertas'])
    expect(
      await screen.findByText(/Ainda não há snapshots diários/, undefined, { timeout: 10_000 }),
    ).toBeInTheDocument()
  }, 20_000)

  it('dá prioridade aos alertas na visão de gestão', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(leadUser),
      'GET /api/health': () => jsonResponse({ status: 'ok', version: '0.1.0' }),
      'GET /api/dashboard/overview': () => jsonResponse(overview()),
    })
    renderRoutes(routes)

    expect(await screen.findByText(/Visão de gestão/)).toBeInTheDocument()
    expect(headings()).toEqual(['Alertas', 'Sprints ativos', 'O meu trabalho'])
  })

  it('não pede o overview sem reports:read', async () => {
    const fetchMock = mockApi({
      'GET /api/users/me': () => jsonResponse(testUser),
      'GET /api/health': () => jsonResponse({ status: 'ok', version: '0.1.0' }),
    })
    renderRoutes(routes)

    expect(await screen.findByText(/Operacional/)).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith('/api/dashboard/overview', expect.anything())
  })
})

describe('Métricas do projeto', () => {
  it('mostra as métricas e aplica os filtros', async () => {
    const fetchMock = mockApi({
      'GET /api/users/me': () => jsonResponse(devUser),
      'GET /api/projects/p1': () => jsonResponse(testProject({ canManage: false })),
      'GET /api/reports/projects/p1/metrics': () => jsonResponse(metrics()),
      'GET /api/reports/projects/p1/metrics?type=bug': () =>
        jsonResponse(metrics({ filters: { ...metrics().filters, type: 'bug' } })),
      'GET /api/reports/projects/p1/metrics?type=bug&from=2025-01-01': () =>
        jsonResponse(
          { title: 'Erro', detail: 'O período não pode exceder 366 dias', field: 'from' },
          422,
        ),
    })
    renderRoutes(routes, '/projects/p1/metrics')

    expect(await screen.findByRole('heading', { name: 'Métricas' })).toBeInTheDocument()
    expect(await screen.findByText('Issue antiga')).toBeInTheDocument()
    expect(screen.getByText(/mediana 5 d · p85 10,2 d · 4 issues/)).toBeInTheDocument()
    expect(screen.getByText('Sem responsável')).toBeInTheDocument()
    expect(screen.getByText('1.4.0')).toBeInTheDocument()
    expect(screen.getByText(/previsibilidade 80%/)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Gravar snapshot de hoje' }),
    ).not.toBeInTheDocument()

    const user = userEvent.setup()
    await user.selectOptions(screen.getByLabelText('Tipo de issue'), 'bug')
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/reports/projects/p1/metrics?type=bug',
        expect.anything(),
      ),
    )
    fireEvent.change(screen.getByLabelText('De'), { target: { value: '2025-01-01' } })
    expect(await screen.findByText('O período não pode exceder 366 dias')).toBeInTheDocument()
  })

  it('grava o snapshot de hoje para quem gere o projeto', async () => {
    const fetchMock = mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(leadUser),
      'GET /api/projects/p1': () => jsonResponse(testProject()),
      'GET /api/reports/projects/p1/metrics': () => jsonResponse(metrics()),
      'POST /api/reports/projects/p1/snapshots': () =>
        jsonResponse(
          {
            projectId: 'p1',
            day: '2026-01-14',
            kpis,
            statusBreakdown: breakdown,
            takenAt: '2026-01-14T10:00:00Z',
          },
          201,
        ),
    })
    renderRoutes(routes, '/projects/p1/metrics')

    const button = await screen.findByRole('button', { name: 'Gravar snapshot de hoje' })
    await userEvent.setup().click(button)

    expect(await screen.findByText('Snapshot de hoje gravado.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/reports/projects/p1/snapshots',
      expect.objectContaining({ method: 'POST' }),
    )
    const nav = screen.getByRole('navigation', { name: /projeto/i })
    expect(within(nav).getByRole('link', { name: 'Métricas' })).toBeInTheDocument()
  })
})
