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

const qaUser = {
  ...testUser,
  id: 'qa1',
  role: 'qa' as const,
  permissions: ['projects:read', 'issues:read', 'tests:read', 'tests:manage', 'tests:execute'],
}
const readerUser = { ...testUser, permissions: ['projects:read', 'issues:read', 'tests:read'] }

const loginIssue = {
  id: 'i1',
  projectId: 'p1',
  key: 'APP-1',
  number: 1,
  type: 'story',
  title: 'Login',
  status: 'todo',
  priority: 'medium',
  assignee: null,
  storyPoints: null,
  labels: [],
  blocked: false,
  dueDate: null,
  parentIssueId: null,
  sprintId: null,
  rank: 1024,
  updatedAt: '2026-01-01T10:00:00Z',
  version: 1,
}

function testCase(overrides: Record<string, unknown> = {}) {
  return {
    id: 'c1',
    projectId: 'p1',
    key: 'TC-1',
    number: 1,
    title: 'Login válido',
    priority: 'high',
    status: 'ready',
    labels: ['auth'],
    stepCount: 1,
    updatedAt: '2026-01-02T10:00:00Z',
    version: 2,
    description: '',
    preconditions: 'Utilizador ativo',
    steps: [{ action: 'Entrar', expectedResult: 'Dashboard' }],
    expectedResult: 'Sessão iniciada',
    issues: [],
    createdAt: '2026-01-01T10:00:00Z',
    canEdit: true,
    ...overrides,
  }
}

function testPlan(overrides: Record<string, unknown> = {}) {
  return {
    id: 'tp1',
    projectId: 'p1',
    name: 'Regressão 1.0',
    description: '',
    status: 'closed',
    testCaseCount: 1,
    createdAt: '2026-01-01T10:00:00Z',
    updatedAt: '2026-01-02T10:00:00Z',
    version: 4,
    testCases: [
      { id: 'c1', key: 'TC-1', title: 'Login válido', priority: 'high', status: 'ready' },
    ],
    issues: [],
    canEdit: true,
    ...overrides,
  }
}

const baseHandlers = (user: typeof qaUser | typeof readerUser) => ({
  ...csrfHandler,
  'GET /api/users/me': () => jsonResponse(user),
  'GET /api/projects/p1': () => jsonResponse(testProject()),
  'GET /api/issues?projectId=p1&sort=number&pageSize=100': () => jsonResponse(pageOf([loginIssue])),
})

describe('casos de teste', () => {
  it('lista os casos com ações de gestão para QA', async () => {
    mockApi({
      ...baseHandlers(qaUser),
      'GET /api/test-cases?projectId=p1&page=1&pageSize=25': () =>
        jsonResponse(pageOf([testCase()])),
    })
    renderRoutes(routes, '/projects/p1/tests')

    const link = await screen.findByRole('link', { name: 'Login válido' })
    expect(link).toHaveAttribute('href', '/projects/p1/tests/cases/c1')
    const row = link.closest('tr')!
    expect(within(row).getByText('TC-1')).toBeInTheDocument()
    expect(within(row).getByText('Pronto')).toBeInTheDocument()
    expect(within(row).getByText('Alta')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Novo caso de teste' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Planos de teste' })).toHaveAttribute(
      'href',
      '/projects/p1/tests/plans',
    )
  })

  it('cria um caso com vários passos e issue ligada', async () => {
    const bodies: unknown[] = []
    mockApi({
      ...baseHandlers(qaUser),
      'POST /api/test-cases': (init) => {
        bodies.push(JSON.parse(String(init.body)))
        return jsonResponse(testCase(), 201)
      },
      'GET /api/test-cases?projectId=p1&page=1&pageSize=25': () => jsonResponse(pageOf([])),
    })
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, '/projects/p1/tests/cases/new')

    await user.click(await screen.findByRole('button', { name: 'Criar caso de teste' }))
    expect(await screen.findByText('Indique o título')).toBeInTheDocument()
    expect(screen.getByText('Indique a ação')).toBeInTheDocument()
    expect(bodies).toHaveLength(0)

    await user.type(screen.getByLabelText('Título'), 'Login válido')
    await user.type(screen.getByLabelText('Ação do passo 1'), 'Abrir login')
    await user.click(screen.getByRole('button', { name: 'Adicionar passo' }))
    await user.type(screen.getByLabelText('Ação do passo 2'), 'Submeter')
    await user.type(screen.getByLabelText('Resultado esperado do passo 2'), 'Dashboard')
    await user.selectOptions(screen.getByLabelText('Prioridade'), 'high')
    await user.type(screen.getByLabelText('Labels'), 'Auth, login, auth')
    await user.selectOptions(await screen.findByLabelText('Issues ligadas'), 'i1')
    expect(screen.getByText('APP-1 · Login')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Criar caso de teste' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/projects/p1/tests'))
    expect(bodies[0]).toEqual({
      projectId: 'p1',
      title: 'Login válido',
      description: '',
      preconditions: '',
      steps: [
        { action: 'Abrir login', expectedResult: '' },
        { action: 'Submeter', expectedResult: 'Dashboard' },
      ],
      expectedResult: '',
      priority: 'high',
      status: 'draft',
      labels: ['auth', 'login'],
      issueIds: ['i1'],
    })
  })

  it('mostra o caso só para consulta sem tests:manage', async () => {
    mockApi({
      ...baseHandlers(readerUser),
      'GET /api/test-cases/c1': () => jsonResponse(testCase({ canEdit: false })),
    })
    renderRoutes(routes, '/projects/p1/tests/cases/c1')

    expect(await screen.findByLabelText('Título')).toBeDisabled()
    expect(screen.getByLabelText('Ação do passo 1')).toHaveValue('Entrar')
    expect(screen.getByText(/Consulta apenas/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Guardar alterações' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Adicionar passo' })).not.toBeInTheDocument()
  })
})

describe('planos de teste', () => {
  it('cria um plano com casos ordenados', async () => {
    const bodies: unknown[] = []
    mockApi({
      ...baseHandlers(qaUser),
      'GET /api/test-cases?projectId=p1&status=draft&status=ready&pageSize=100': () =>
        jsonResponse(
          pageOf([testCase(), testCase({ id: 'c2', key: 'TC-2', title: 'Logout' })], 1, 100),
        ),
      'POST /api/test-plans': (init) => {
        bodies.push(JSON.parse(String(init.body)))
        return jsonResponse(testPlan({ status: 'draft' }), 201)
      },
      'GET /api/test-plans?projectId=p1&page=1&pageSize=25': () => jsonResponse(pageOf([])),
    })
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, '/projects/p1/tests/plans/new')

    await user.type(await screen.findByLabelText('Nome'), 'Regressão 1.0')
    const picker = screen.getByLabelText('Adicionar caso')
    await waitFor(() => expect(within(picker).getAllByRole('option')).toHaveLength(3))
    await user.selectOptions(picker, 'c1')
    await user.selectOptions(screen.getByLabelText('Adicionar caso'), 'c2')
    await user.click(screen.getByRole('button', { name: 'Subir TC-2' }))
    await user.click(screen.getByRole('button', { name: 'Criar plano de teste' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/projects/p1/tests/plans'))
    expect(bodies[0]).toEqual({
      projectId: 'p1',
      name: 'Regressão 1.0',
      description: '',
      status: 'draft',
      testCaseIds: ['c2', 'c1'],
      issueIds: [],
    })
  })

  it('num plano fechado só envia a mudança de estado', async () => {
    const bodies: unknown[] = []
    mockApi({
      ...baseHandlers(qaUser),
      'GET /api/test-plans/tp1': () => jsonResponse(testPlan()),
      'PATCH /api/test-plans/tp1': (init) => {
        bodies.push(JSON.parse(String(init.body)))
        return jsonResponse(testPlan({ status: 'active', version: 5 }))
      },
      'GET /api/test-plans?projectId=p1&page=1&pageSize=25': () => jsonResponse(pageOf([])),
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/tests/plans/tp1')

    expect(await screen.findByLabelText('Nome')).toHaveAttribute('readonly')
    expect(screen.getByText(/mude o estado para o reabrir/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Adicionar caso')).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Estado'), 'active')
    await user.click(screen.getByRole('button', { name: 'Guardar alterações' }))

    await waitFor(() => expect(bodies).toEqual([{ status: 'active', version: 4 }]))
  })
})
