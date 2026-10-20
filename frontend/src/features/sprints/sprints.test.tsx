import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { routes } from '@/app/router'
import {
  csrfHandler,
  jsonResponse,
  mockApi,
  pageOf,
  renderRoutes,
  techLeadUser,
  testProject,
  testUser,
} from '@/test/utils'

const sprintManager = { ...techLeadUser, permissions: [...techLeadUser.permissions, 'sprints:manage'] }

function testSprint(overrides: Record<string, unknown> = {}) {
  return {
    id: 's1',
    projectId: 'p1',
    name: 'Sprint 1',
    goal: 'Concluir autenticação',
    status: 'planned',
    startDate: '2099-01-02',
    endDate: '2099-01-15',
    durationDays: 14,
    capacityStoryPoints: null,
    scope: {
      issueCount: 0,
      storyPoints: 0,
      unestimatedCount: 0,
      completedIssueCount: 0,
      completedStoryPoints: 0,
    },
    committedStoryPoints: null,
    committedIssueCount: null,
    startedAt: null,
    closedAt: null,
    result: null,
    retrospective: null,
    createdAt: '2026-01-01T10:00:00Z',
    updatedAt: '2026-01-01T10:00:00Z',
    version: 1,
    canEdit: true,
    ...overrides,
  }
}

describe('lista de sprints', () => {
  it('mostra os sprints e as ações de gestão com sprints:manage', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(sprintManager),
      'GET /api/projects/p1': () => jsonResponse(testProject()),
      'GET /api/sprints?projectId=p1&page=1&pageSize=25': () =>
        jsonResponse(
          pageOf([testSprint(), testSprint({ id: 's0', name: 'Sprint 0', status: 'closed', canEdit: false })]),
        ),
    })
    renderRoutes(routes, '/projects/p1/sprints')

    const row = (await screen.findByText('Sprint 1')).closest('tr')!
    expect(within(row).getByText('Planeado')).toBeInTheDocument()
    expect(within(row).getByText('Concluir autenticação')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Editar Sprint 1' })).toHaveAttribute(
      'href',
      '/projects/p1/sprints/s1/edit',
    )
    expect(screen.queryByRole('link', { name: 'Editar Sprint 0' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Novo sprint' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sprint 1' })).toHaveAttribute(
      'href',
      '/projects/p1/sprints/s1',
    )
  })

  it('esconde as ações sem permissão e mostra estado vazio', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(testUser),
      'GET /api/projects/p1': () => jsonResponse(testProject({ canManage: false })),
      'GET /api/sprints?projectId=p1&page=1&pageSize=25': () => jsonResponse(pageOf([])),
    })
    renderRoutes(routes, '/projects/p1/sprints')

    expect(await screen.findByText('Nenhum sprint encontrado.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Novo sprint' })).not.toBeInTheDocument()
  })
})

describe('formulário de sprint', () => {
  it('sugere nome e datas a seguir ao último sprint e cria', async () => {
    const bodies: unknown[] = []
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(sprintManager),
      'GET /api/projects/p1': () => jsonResponse(testProject()),
      'GET /api/sprints?projectId=p1&page=1&pageSize=1': () =>
        jsonResponse({ ...pageOf([testSprint()], 1, 1), total: 3 }),
      'POST /api/sprints': (init) => {
        bodies.push(JSON.parse(String(init.body)))
        return jsonResponse(testSprint({ id: 's4', name: 'Sprint 4' }), 201)
      },
      'GET /api/sprints?projectId=p1&page=1&pageSize=25': () => jsonResponse(pageOf([])),
    })
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, '/projects/p1/sprints/new')

    expect(await screen.findByLabelText('Nome')).toHaveValue('Sprint 4')
    expect(screen.getByLabelText('Data de início')).toHaveValue('2099-01-16')
    expect(screen.getByLabelText('Data de fim')).toHaveValue('2099-01-29')

    await user.clear(screen.getByLabelText('Data de início'))
    await user.type(screen.getByLabelText('Data de início'), '2099-02-01')
    expect(screen.getByLabelText('Data de fim')).toHaveValue('2099-02-14')
    await user.type(screen.getByLabelText('Objetivo'), 'Entregar sprints')
    await user.type(screen.getByLabelText('Capacidade (story points)'), '21.5')
    await user.click(screen.getByRole('button', { name: 'Criar sprint' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/projects/p1/sprints'))
    expect(bodies[0]).toEqual({
      projectId: 'p1',
      name: 'Sprint 4',
      goal: 'Entregar sprints',
      startDate: '2099-02-01',
      endDate: '2099-02-14',
      capacityStoryPoints: 21.5,
    })
  })

  it('valida as datas e mostra erros do servidor por campo', async () => {
    let posted = 0
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(sprintManager),
      'GET /api/projects/p1': () => jsonResponse(testProject()),
      'GET /api/sprints?projectId=p1&page=1&pageSize=1': () => jsonResponse(pageOf([], 1, 1)),
      'POST /api/sprints': () => {
        posted += 1
        return jsonResponse(
          { title: 'Regra', detail: 'As datas sobrepõem-se ao sprint Sprint 1', field: 'startDate' },
          422,
        )
      },
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/sprints/new')

    const end = await screen.findByLabelText('Data de fim')
    await user.clear(end)
    await user.type(end, '2000-01-01')
    await user.click(screen.getByRole('button', { name: 'Criar sprint' }))
    expect(await screen.findByText(/não pode ser anterior/)).toBeInTheDocument()
    expect(posted).toBe(0)

    await user.clear(end)
    await user.type(end, '2099-01-01')
    await user.clear(screen.getByLabelText('Data de início'))
    await user.type(screen.getByLabelText('Data de início'), '2098-12-20')
    await user.click(screen.getByRole('button', { name: 'Criar sprint' }))
    expect(await screen.findAllByText(/sobrepõem-se ao sprint Sprint 1/)).not.toHaveLength(0)
    expect(posted).toBe(1)
  })

  it('edita um sprint ativo sem enviar a data de início e mostra conflitos', async () => {
    const bodies: unknown[] = []
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(sprintManager),
      'GET /api/projects/p1': () => jsonResponse(testProject()),
      'GET /api/sprints/s1': () => jsonResponse(testSprint({ status: 'active', version: 2 })),
      'PATCH /api/sprints/s1': (init) => {
        bodies.push(JSON.parse(String(init.body)))
        return jsonResponse({ title: 'Conflito', detail: 'Alterado', currentVersion: 3 }, 409)
      },
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/sprints/s1/edit')

    expect(await screen.findByLabelText('Data de início')).toHaveAttribute('readonly')
    expect(screen.getByText(/a data de início já não pode ser alterada/)).toBeInTheDocument()
    await user.clear(screen.getByLabelText('Data de fim'))
    await user.type(screen.getByLabelText('Data de fim'), '2099-01-20')
    await user.click(screen.getByRole('button', { name: 'Guardar alterações' }))

    expect(await screen.findByText(/alterados por outra pessoa/)).toBeInTheDocument()
    expect(bodies[0]).toEqual({
      name: 'Sprint 1',
      goal: 'Concluir autenticação',
      endDate: '2099-01-20',
      capacityStoryPoints: null,
      version: 2,
    })
  })
})

function testIssue(overrides: Record<string, unknown> = {}) {
  return {
    id: 'i1',
    projectId: 'p1',
    key: 'APP-1',
    number: 1,
    type: 'story',
    title: 'Login com SSO',
    status: 'todo',
    priority: 'medium',
    assignee: null,
    storyPoints: 3,
    labels: [],
    blocked: false,
    dueDate: null,
    parentIssueId: null,
    sprintId: null,
    rank: 1024,
    updatedAt: '2026-01-02T10:00:00Z',
    version: 1,
    ...overrides,
  }
}

const SPRINT_ISSUES = 'GET /api/issues?projectId=p1&sprintId=s1&sort=rank&pageSize=100'
const BACKLOG =
  'GET /api/issues?projectId=p1&sprintId=none&status=todo&status=in_progress&status=code_review' +
  '&status=testing&type=story&type=task&type=bug&type=spike&type=improvement&type=subtask' +
  '&sort=rank&pageSize=100'

describe('planeamento do sprint', () => {
  it('mostra totais face à capacidade e associa/remove issues', async () => {
    const added: unknown[] = []
    let removed = 0
    const scope = {
      issueCount: 1,
      storyPoints: 8,
      unestimatedCount: 0,
      completedIssueCount: 0,
      completedStoryPoints: 0,
    }
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(sprintManager),
      'GET /api/projects/p1': () => jsonResponse(testProject()),
      'GET /api/sprints/s1': () => jsonResponse(testSprint({ capacityStoryPoints: 5, scope })),
      [SPRINT_ISSUES]: () => jsonResponse(pageOf([testIssue({ sprintId: 's1', storyPoints: 8 })], 1, 100)),
      [BACKLOG]: () => jsonResponse(pageOf([testIssue({ id: 'i2', key: 'APP-2', title: 'Logout' })], 1, 100)),
      'POST /api/sprints/s1/issues': (init) => {
        added.push(JSON.parse(String(init.body)))
        return jsonResponse(testSprint())
      },
      'DELETE /api/sprints/s1/issues/i1': () => {
        removed += 1
        return jsonResponse(testSprint())
      },
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/sprints/s1')

    expect(await screen.findByText('Capacidade: 5')).toBeInTheDocument()
    expect(screen.getByText(/excede a capacidade do sprint em 3 story points/)).toBeInTheDocument()
    expect(await screen.findByText('Logout')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Adicionar APP-2 ao sprint' }))
    await waitFor(() => expect(added).toEqual([{ issueIds: ['i2'] }]))
    await user.click(screen.getByRole('button', { name: 'Remover APP-1 do sprint' }))
    await waitFor(() => expect(removed).toBe(1))
  })

  it('estima em linha com controlo de versão', async () => {
    const bodies: unknown[] = []
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(sprintManager),
      'GET /api/projects/p1': () => jsonResponse(testProject()),
      'GET /api/sprints/s1': () => jsonResponse(testSprint()),
      [SPRINT_ISSUES]: () =>
        jsonResponse(pageOf([testIssue({ sprintId: 's1', storyPoints: null, version: 4 })], 1, 100)),
      [BACKLOG]: () => jsonResponse(pageOf([], 1, 100)),
      'PATCH /api/issues/i1': (init) => {
        bodies.push(JSON.parse(String(init.body)))
        return jsonResponse(testIssue({ storyPoints: 5, version: 5 }))
      },
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/sprints/s1')

    const input = await screen.findByLabelText('Story points de APP-1')
    await user.type(input, '2.3{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('múltiplos de 0,5')
    expect(bodies).toHaveLength(0)

    await user.type(input, '5{Enter}')
    await waitFor(() => expect(bodies).toEqual([{ version: 4, storyPoints: 5 }]))
  })

  it('sem gestão de sprints só consulta', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(testUser),
      'GET /api/projects/p1': () => jsonResponse(testProject({ canManage: false })),
      'GET /api/sprints/s1': () => jsonResponse(testSprint({ canEdit: false })),
      [SPRINT_ISSUES]: () => jsonResponse(pageOf([testIssue({ sprintId: 's1' })], 1, 100)),
    })
    renderRoutes(routes, '/projects/p1/sprints/s1')

    expect(await screen.findByText('Login com SSO')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Remover/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Backlog' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Story points de APP-1')).not.toBeInTheDocument()
  })
})

describe('início do sprint', () => {
  const scope = {
    issueCount: 2,
    storyPoints: 8,
    unestimatedCount: 1,
    completedIssueCount: 0,
    completedStoryPoints: 0,
  }

  it('pede confirmação, envia a versão e mostra erros', async () => {
    const bodies: unknown[] = []
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(sprintManager),
      'GET /api/projects/p1': () => jsonResponse(testProject()),
      'GET /api/sprints/s1': () => jsonResponse(testSprint({ scope, version: 3 })),
      [SPRINT_ISSUES]: () => jsonResponse(pageOf([], 1, 100)),
      [BACKLOG]: () => jsonResponse(pageOf([], 1, 100)),
      'POST /api/sprints/s1/start': (init) => {
        bodies.push(JSON.parse(String(init.body)))
        return jsonResponse(
          { title: 'Regra', detail: 'Já existe um sprint ativo neste projeto', field: 'status' },
          422,
        )
      },
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/sprints/s1')

    await user.click(await screen.findByRole('button', { name: 'Iniciar sprint' }))
    expect(screen.getByText(/2 issues e 8 story points \(1 sem estimativa contam como 0\)/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Confirmar início' }))

    expect(await screen.findByText(/Já existe um sprint ativo/)).toBeInTheDocument()
    expect(bodies).toEqual([{ version: 3 }])
  })

  it('não deixa iniciar um sprint vazio', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(sprintManager),
      'GET /api/projects/p1': () => jsonResponse(testProject()),
      'GET /api/sprints/s1': () => jsonResponse(testSprint()),
      [SPRINT_ISSUES]: () => jsonResponse(pageOf([], 1, 100)),
      [BACKLOG]: () => jsonResponse(pageOf([], 1, 100)),
    })
    renderRoutes(routes, '/projects/p1/sprints/s1')

    expect(await screen.findByRole('button', { name: 'Iniciar sprint' })).toBeDisabled()
    expect(screen.getByText('Associe issues antes de iniciar.')).toBeInTheDocument()
  })

  it('mostra o compromisso de um sprint ativo e a ligação ao quadro', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(sprintManager),
      'GET /api/projects/p1': () => jsonResponse(testProject()),
      'GET /api/sprints/s1': () =>
        jsonResponse(
          testSprint({ status: 'active', startedAt: '2099-01-02T09:00:00Z', scope, version: 2 }),
        ),
      'GET /api/sprints/s1/commitment': () =>
        jsonResponse({
          sprintId: 's1',
          takenAt: '2099-01-02T09:00:00Z',
          issueCount: 2,
          storyPoints: 8,
          unestimatedCount: 0,
          removedCount: 1,
          addedCount: 1,
          addedStoryPoints: 2,
          issues: [
            {
              issueId: 'i1',
              key: 'APP-1',
              title: 'Login com SSO',
              type: 'story',
              status: 'todo',
              storyPoints: 5,
              currentStatus: 'in_progress',
              currentStoryPoints: 8,
              inSprint: true,
            },
            {
              issueId: 'i2',
              key: 'APP-2',
              title: 'Logout',
              type: 'story',
              status: 'todo',
              storyPoints: 3,
              currentStatus: 'todo',
              currentStoryPoints: 3,
              inSprint: false,
            },
          ],
          added: [
            { issueId: 'i3', key: 'APP-3', title: 'Perfil', type: 'task', status: 'todo', storyPoints: 2 },
          ],
        }),
      [SPRINT_ISSUES]: () => jsonResponse(pageOf([], 1, 100)),
      [BACKLOG]: () => jsonResponse(pageOf([], 1, 100)),
    })
    renderRoutes(routes, '/projects/p1/sprints/s1')

    expect(await screen.findByRole('heading', { name: 'Compromisso' })).toBeInTheDocument()
    expect(screen.getByText(/1 adicionadas \(2 SP\) e 1\s+retiradas/)).toBeInTheDocument()
    expect(screen.getByText('5 → 8')).toBeInTheDocument()
    expect(screen.getByText('(retirada)')).toBeInTheDocument()
    expect(screen.getByText('(adicionada)')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Iniciar sprint' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver quadro' })).toHaveAttribute(
      'href',
      '/projects/p1/board?sprintId=s1',
    )
  })
})

describe('fecho do sprint', () => {
  const scope = {
    issueCount: 3,
    storyPoints: 10,
    unestimatedCount: 0,
    completedIssueCount: 1,
    completedStoryPoints: 5,
  }
  const active = () =>
    testSprint({ status: 'active', startedAt: '2099-01-02T09:00:00Z', scope, version: 4 })
  const commitment = {
    sprintId: 's1',
    takenAt: '2099-01-02T09:00:00Z',
    issueCount: 0,
    storyPoints: 0,
    unestimatedCount: 0,
    removedCount: 0,
    addedCount: 0,
    addedStoryPoints: 0,
    issues: [],
    added: [],
  }
  const PLANNED = 'GET /api/sprints?projectId=p1&status=planned&sort=startDate&pageSize=50'

  it('fecha com destino e retrospetiva e mostra erros por campo', async () => {
    const bodies: unknown[] = []
    let attempts = 0
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(sprintManager),
      'GET /api/projects/p1': () => jsonResponse(testProject()),
      'GET /api/sprints/s1': () => jsonResponse(active()),
      'GET /api/sprints/s1/commitment': () => jsonResponse(commitment),
      [SPRINT_ISSUES]: () => jsonResponse(pageOf([], 1, 100)),
      [BACKLOG]: () => jsonResponse(pageOf([], 1, 100)),
      [PLANNED]: () =>
        jsonResponse(pageOf([testSprint({ id: 's2', name: 'Sprint 2', startDate: '2099-01-16' })], 1, 50)),
      'POST /api/sprints/s1/close': (init) => {
        bodies.push(JSON.parse(String(init.body)))
        attempts += 1
        if (attempts === 1) {
          return jsonResponse(
            { title: 'Regra', detail: 'Sprint de destino inválido', field: 'carryOverSprintId' },
            422,
          )
        }
        return jsonResponse(testSprint({ status: 'closed', canEdit: false, version: 5 }))
      },
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/sprints/s1')

    await user.click(await screen.findByRole('link', { name: 'Fechar sprint' }))
    expect(await screen.findByText(/1 issues concluídas \(5 story points\)/)).toBeInTheDocument()
    expect(screen.getByText(/2 issues por concluir \(\s*5 story points\)/)).toBeInTheDocument()
    await user.selectOptions(
      await screen.findByLabelText('Destino das issues por concluir'),
      await screen.findByRole('option', { name: /Sprint 2/ }),
    )
    await user.type(screen.getByLabelText('O que correu bem'), 'Entregas')
    await user.click(screen.getByRole('button', { name: 'Fechar sprint' }))

    expect((await screen.findAllByText('Sprint de destino inválido')).length).toBeGreaterThan(0)
    await user.click(screen.getByRole('button', { name: 'Fechar sprint' }))

    await waitFor(() => expect(attempts).toBe(2))
    expect(bodies[1]).toEqual({
      version: 4,
      carryOverSprintId: 's2',
      retrospective: { wentWell: 'Entregas', toImprove: '', actions: '' },
    })
  })

  it('mostra o resultado e a retrospetiva de um sprint fechado', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(sprintManager),
      'GET /api/projects/p1': () => jsonResponse(testProject()),
      'GET /api/sprints/s1': () =>
        jsonResponse(
          testSprint({
            status: 'closed',
            canEdit: false,
            closedAt: '2099-01-15T17:00:00Z',
            result: {
              completedIssueCount: 4,
              completedStoryPoints: 13,
              carriedOverIssueCount: 2,
              carriedOverStoryPoints: 5,
              carryOverSprintId: null,
              committedCompletedIssueCount: 3,
              committedCompletedStoryPoints: 8,
            },
            retrospective: { wentWell: 'Boa colaboração', toImprove: '', actions: 'Rever estimativas' },
          }),
        ),
      'GET /api/sprints/s1/commitment': () => jsonResponse(commitment),
      [SPRINT_ISSUES]: () => jsonResponse(pageOf([], 1, 100)),
    })
    renderRoutes(routes, '/projects/p1/sprints/s1')

    expect(await screen.findByRole('heading', { name: 'Resultado' })).toBeInTheDocument()
    expect(screen.getByText('13 story points')).toBeInTheDocument()
    expect(screen.getByText('5 story points para o backlog')).toBeInTheDocument()
    expect(screen.getByText('Boa colaboração')).toBeInTheDocument()
    expect(screen.getByText('Rever estimativas')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Fechar sprint' })).not.toBeInTheDocument()
  })
})

describe('dashboard do sprint', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    )
  })

  const report = {
    sprintId: 's1',
    name: 'Sprint 1',
    goal: 'Concluir autenticação',
    status: 'active',
    startDate: '2099-01-02',
    endDate: '2099-01-04',
    asOf: '2099-01-03T10:00:00Z',
    kpis: {
      committedIssueCount: 3,
      committedStoryPoints: 8,
      issueCount: 3,
      storyPoints: 10,
      unestimatedCount: 1,
      completedIssueCount: 1,
      completedStoryPoints: 5,
      remainingStoryPoints: 5,
      progressPercent: 50,
      totalDays: 3,
      elapsedDays: 2,
      remainingDays: 1,
      blockedCount: 1,
      addedCount: 1,
      removedCount: 1,
    },
    burndown: [
      { day: '2099-01-02', ideal: 8, remaining: 8, scope: 8 },
      { day: '2099-01-03', ideal: 4, remaining: 5, scope: 10 },
      { day: '2099-01-04', ideal: 0, remaining: null, scope: null },
    ],
    statusBreakdown: [
      { status: 'todo', issueCount: 1, storyPoints: 3 },
      { status: 'in_progress', issueCount: 1, storyPoints: 2 },
      { status: 'code_review', issueCount: 0, storyPoints: 0 },
      { status: 'testing', issueCount: 0, storyPoints: 0 },
      { status: 'done', issueCount: 1, storyPoints: 5 },
    ],
    blockedIssues: [
      {
        issueId: 'i2',
        key: 'APP-2',
        title: 'Logout',
        status: 'todo',
        blockReason: 'Aguarda API',
        blockedAt: '2099-01-03T09:00:00Z',
      },
    ],
    velocity: [
      {
        sprintId: 's0',
        name: 'Sprint 0',
        committedStoryPoints: 10,
        completedStoryPoints: 7.5,
        committedCompletedStoryPoints: 6,
        predictabilityPercent: 60,
      },
    ],
    averageVelocity: 7.5,
  }

  it('mostra KPIs, bloqueios e velocidade a partir do detalhe', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(testUser),
      'GET /api/projects/p1': () => jsonResponse(testProject({ canManage: false })),
      'GET /api/sprints/s1': () =>
        jsonResponse(testSprint({ status: 'active', startedAt: '2099-01-02T09:00:00Z', canEdit: false })),
      'GET /api/sprints/s1/commitment': () =>
        jsonResponse({
          sprintId: 's1',
          takenAt: '2099-01-02T09:00:00Z',
          issueCount: 0,
          storyPoints: 0,
          unestimatedCount: 0,
          removedCount: 0,
          addedCount: 0,
          addedStoryPoints: 0,
          issues: [],
          added: [],
        }),
      [SPRINT_ISSUES]: () => jsonResponse(pageOf([], 1, 100)),
      'GET /api/reports/sprints/s1': () => jsonResponse(report),
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/sprints/s1')

    await user.click(await screen.findByRole('link', { name: 'Ver dashboard' }))

    expect(await screen.findByRole('heading', { name: 'Dashboard · Sprint 1' })).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(screen.getByText('5 de 10 story points')).toBeInTheDocument()
    expect(screen.getByText('3 issues · 1 adicionadas, 1 retiradas')).toBeInTheDocument()
    expect(screen.getByText('2 de 3 dias decorridos')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Gráfico de burndown' })).toBeInTheDocument()
    expect(screen.getByText('1 · 5 SP')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'APP-2' })).toHaveAttribute('href', '/issues/APP-2')
    expect(screen.getByText('Aguarda API')).toBeInTheDocument()
    expect(screen.getByText(/Média: 7,5 story points/)).toBeInTheDocument()
    expect(screen.getByText('60%')).toBeInTheDocument()
  })

  it('explica que o dashboard só existe depois do início', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(testUser),
      'GET /api/projects/p1': () => jsonResponse(testProject({ canManage: false })),
      'GET /api/sprints/s1': () => jsonResponse(testSprint({ canEdit: false })),
      'GET /api/reports/sprints/s1': () =>
        jsonResponse({ title: 'Regra', detail: 'O sprint ainda não foi iniciado', field: 'status' }, 422),
    })
    renderRoutes(routes, '/projects/p1/sprints/s1/dashboard')

    expect(
      await screen.findByText('O dashboard fica disponível depois de iniciar o sprint.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voltar ao sprint' })).toHaveAttribute(
      'href',
      '/projects/p1/sprints/s1',
    )
  })
})
