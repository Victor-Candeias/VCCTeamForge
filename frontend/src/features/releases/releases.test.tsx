import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { routes } from '@/app/router'
import {
  csrfHandler,
  jsonResponse,
  mockApi,
  pageOf,
  renderRoutes,
  testProject,
  testUser,
} from '@/test/utils'

const leadUser = {
  ...testUser,
  id: 'tl1',
  role: 'tech_lead' as const,
  permissions: [
    'projects:read',
    'issues:read',
    'tests:read',
    'releases:read',
    'releases:manage',
    'releases:approve',
  ],
}
const readerUser = { ...testUser, permissions: ['projects:read', 'issues:read', 'releases:read'] }
const lead = { id: 'tl1', name: 'Tiago', email: 'tiago@exemplo.pt', role: 'tech_lead' }

function releaseSummary(overrides: Record<string, unknown> = {}) {
  return {
    id: 'r1',
    projectId: 'p1',
    name: '1.4.0',
    status: 'ready_for_qa',
    plannedDate: '2026-11-30',
    releasedAt: null,
    issueCount: 1,
    knownBugCount: 1,
    checklistDone: 1,
    checklistTotal: 2,
    createdAt: '2026-01-01T10:00:00Z',
    updatedAt: '2026-01-02T10:00:00Z',
    version: 3,
    ...overrides,
  }
}

function release(overrides: Record<string, unknown> = {}) {
  return {
    ...releaseSummary(),
    description: 'Versão de outono',
    notes: '## Novidades\n\n- Login com SSO',
    issues: [{ id: 'i1', key: 'APP-1', title: 'Login SSO', type: 'story', status: 'done' }],
    knownBugs: [{ id: 'i2', key: 'APP-2', title: 'Erro raro', type: 'bug', status: 'todo' }],
    testPlans: [{ id: 'tp1', name: 'Regressão', status: 'active' }],
    checklist: [
      {
        id: 'k1',
        label: 'Testes de regressão executados',
        required: true,
        done: true,
        doneBy: lead,
        doneAt: '2026-01-02T10:00:00Z',
      },
      {
        id: 'k2',
        label: 'Notas de release revistas',
        required: true,
        done: false,
        doneBy: null,
        doneAt: null,
      },
    ],
    criteria: { issuesDone: true, testsPassed: true, noOpenCriticalBugs: false },
    quality: {
      issues: { total: 1, done: 1 },
      knownBugs: { total: 1, open: 1, openCritical: 0 },
      tests: {
        plans: 1,
        totalCases: 2,
        executedCases: 2,
        counts: { pass: 1, fail: 1, blocked: 0, not_run: 0, skipped: 0 },
        passRate: 0.5,
        regressions: 1,
      },
      criteria: [
        {
          key: 'issuesDone',
          label: 'Todas as issues incluídas concluídas',
          enabled: true,
          passed: true,
          detail: '1/1 issues concluídas',
        },
        {
          key: 'testsPassed',
          label: 'Testes dos planos associados aprovados',
          enabled: true,
          passed: false,
          detail: '1/2 casos aprovados',
        },
        {
          key: 'noOpenCriticalBugs',
          label: 'Sem bugs críticos em aberto',
          enabled: false,
          passed: true,
          detail: '0 bugs críticos em aberto',
        },
      ],
      ready: false,
    },
    history: [
      {
        action: 'submitted',
        fromStatus: 'draft',
        toStatus: 'ready_for_qa',
        fields: [],
        comment: '',
        user: lead,
        at: '2026-01-02T10:00:00Z',
      },
      {
        action: 'created',
        fromStatus: null,
        toStatus: null,
        fields: [],
        comment: '',
        user: lead,
        at: '2026-01-01T10:00:00Z',
      },
    ],
    canEdit: true,
    availableTransitions: ['approved', 'draft'],
    ...overrides,
  }
}

const baseHandlers = (user: typeof leadUser | typeof readerUser) => ({
  ...csrfHandler,
  'GET /api/users/me': () => jsonResponse(user),
  'GET /api/projects/p1': () => jsonResponse(testProject()),
})

describe('releases', () => {
  it('lista releases e filtra por estado', async () => {
    mockApi({
      ...baseHandlers(leadUser),
      'GET /api/releases?projectId=p1&page=1&pageSize=25': () =>
        jsonResponse(
          pageOf([
            releaseSummary(),
            releaseSummary({ id: 'r2', name: '1.3.0', status: 'released' }),
          ]),
        ),
      'GET /api/releases?projectId=p1&status=released&page=1&pageSize=25': () =>
        jsonResponse(pageOf([releaseSummary({ id: 'r2', name: '1.3.0', status: 'released' })])),
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/releases')

    expect(await screen.findByRole('link', { name: '1.4.0' })).toHaveAttribute(
      'href',
      '/projects/p1/releases/r1',
    )
    expect(screen.getByRole('link', { name: 'Nova release' })).toBeInTheDocument()
    expect(screen.getAllByText('1/2')).toHaveLength(2)

    await user.selectOptions(screen.getByLabelText('Estado'), 'released')
    await waitFor(() =>
      expect(screen.queryByRole('link', { name: '1.4.0' })).not.toBeInTheDocument(),
    )
    expect(screen.getByRole('link', { name: '1.3.0' })).toBeInTheDocument()
  })

  it('cria uma release com checklist herdada e critérios', async () => {
    const bodies: unknown[] = []
    mockApi({
      ...baseHandlers(leadUser),
      'GET /api/issues?projectId=p1&sort=number&pageSize=100': () =>
        jsonResponse(
          pageOf([{ id: 'i1', key: 'APP-1', title: 'Login SSO', type: 'story', status: 'done' }]),
        ),
      'GET /api/issues?projectId=p1&type=bug&sort=number&pageSize=100': () =>
        jsonResponse(pageOf([])),
      'GET /api/test-plans?projectId=p1&pageSize=100': () =>
        jsonResponse(pageOf([{ id: 'tp1', name: 'Regressão', status: 'active' }])),
      'POST /api/releases': (init) => {
        bodies.push(JSON.parse(String(init.body)))
        return jsonResponse(release({ status: 'draft' }), 201)
      },
      'GET /api/releases/r1': () => jsonResponse(release({ status: 'draft' })),
    })
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, '/projects/p1/releases/new')

    await user.type(await screen.findByLabelText('Versão'), 'versão 1')
    await user.click(screen.getByRole('button', { name: 'Criar release' }))
    expect(await screen.findByText(/Use apenas letras/)).toBeInTheDocument()

    await user.clear(screen.getByLabelText('Versão'))
    await user.type(screen.getByLabelText('Versão'), '1.4.0')
    await user.type(screen.getByLabelText('Data prevista'), '2026-11-30')
    await screen.findByRole('option', { name: 'APP-1 · Login SSO' })
    await user.selectOptions(screen.getByLabelText('Issues incluídas'), 'i1')
    await screen.findByRole('option', { name: 'Regressão' })
    await user.selectOptions(screen.getByLabelText('Planos de teste'), 'tp1')
    await user.click(screen.getByLabelText('Sem bugs críticos em aberto'))
    expect(screen.getByText(/é usada a checklist da release anterior/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Criar release' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/projects/p1/releases/r1'))
    expect(bodies[0]).toEqual({
      projectId: 'p1',
      name: '1.4.0',
      plannedDate: '2026-11-30',
      description: '',
      notes: '',
      issueIds: ['i1'],
      knownBugIds: [],
      testPlanIds: ['tp1'],
      criteria: { issuesDone: true, testsPassed: true, noOpenCriticalBugs: false },
    })
  })

  it('mostra qualidade, marca a checklist e executa transições', async () => {
    const patches: unknown[] = []
    const transitions: unknown[] = []
    mockApi({
      ...baseHandlers(leadUser),
      'GET /api/releases/r1': () => jsonResponse(release()),
      'PATCH /api/releases/r1': (init) => {
        patches.push(JSON.parse(String(init.body)))
        return jsonResponse(release({ version: 4 }))
      },
      'POST /api/releases/r1/transitions': (init) => {
        transitions.push(JSON.parse(String(init.body)))
        return jsonResponse(
          {
            title: 'Regra de negócio violada',
            detail: 'Critérios de aprovação não cumpridos',
            field: 'criteria',
          },
          422,
        )
      },
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/releases/r1')

    expect(await screen.findByRole('heading', { name: 'Release 1.4.0' })).toBeInTheDocument()
    const criteria = screen.getByRole('list', { name: 'Critérios de aprovação' })
    expect(within(criteria).getByText(/1\/2 casos aprovados \(por cumprir\)/)).toBeInTheDocument()
    expect(within(criteria).getByText(/\(não exigido\)/)).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'APP-1 · Login SSO' })).toHaveAttribute(
      'href',
      '/issues/APP-1',
    )
    expect(screen.getByText('Enviada para QA')).toBeInTheDocument()

    await user.click(screen.getByLabelText('Notas de release revistas'))
    await waitFor(() => expect(patches).toHaveLength(1))
    expect(patches[0]).toEqual({
      version: 3,
      checklist: [
        { id: 'k1', label: 'Testes de regressão executados', required: true, done: true },
        { id: 'k2', label: 'Notas de release revistas', required: true, done: true },
      ],
    })

    await user.click(await screen.findByRole('button', { name: 'Rejeitar' }))
    expect(screen.getByText('Indique o motivo')).toBeInTheDocument()
    expect(transitions).toHaveLength(0)

    await user.click(screen.getByRole('button', { name: 'Aprovar' }))
    expect(await screen.findByText('Critérios de aprovação não cumpridos')).toBeInTheDocument()
    expect(transitions[0]).toEqual({ to: 'approved', comment: '', version: 4 })
  })

  it('mostra a release só para consulta sem permissões', async () => {
    mockApi({
      ...baseHandlers(readerUser),
      'GET /api/releases/r1': () =>
        jsonResponse(release({ canEdit: false, availableTransitions: [] })),
    })
    renderRoutes(routes, '/projects/p1/releases/r1')

    expect(await screen.findByRole('heading', { name: 'Release 1.4.0' })).toBeInTheDocument()
    expect(screen.getByLabelText('Notas de release revistas')).toBeDisabled()
    expect(
      screen.queryAllByRole('link').filter((link) => link.getAttribute('href')?.endsWith('/edit')),
    ).toEqual([expect.objectContaining({ href: expect.stringContaining('/projects/p1/edit') })])
    expect(screen.queryByRole('button', { name: 'Aprovar' })).not.toBeInTheDocument()
  })
})
