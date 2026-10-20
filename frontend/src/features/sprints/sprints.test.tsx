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
    committedStoryPoints: null,
    committedIssueCount: null,
    startedAt: null,
    closedAt: null,
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
    await user.click(screen.getByRole('button', { name: 'Criar sprint' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/projects/p1/sprints'))
    expect(bodies[0]).toEqual({
      projectId: 'p1',
      name: 'Sprint 4',
      goal: 'Entregar sprints',
      startDate: '2099-02-01',
      endDate: '2099-02-14',
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
      version: 2,
    })
  })
})
