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
  permissions: [
    'projects:read',
    'issues:read',
    'issues:write',
    'tests:read',
    'tests:manage',
    'tests:execute',
  ],
}
const readerUser = { ...testUser, permissions: ['projects:read', 'issues:read', 'tests:read'] }
const qa = { id: 'qa1', name: 'Quitéria', email: 'qa@exemplo.pt' }

function testCase(overrides: Record<string, unknown> = {}) {
  return {
    id: 'c1',
    projectId: 'p1',
    key: 'TC-1',
    number: 1,
    title: 'Login válido',
    priority: 'high',
    status: 'ready',
    labels: [],
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
    status: 'active',
    testCaseCount: 2,
    createdAt: '2026-01-01T10:00:00Z',
    updatedAt: '2026-01-02T10:00:00Z',
    version: 2,
    testCases: [
      { id: 'c1', key: 'TC-1', title: 'Login válido', priority: 'high', status: 'ready' },
      { id: 'c2', key: 'TC-2', title: 'Logout', priority: 'medium', status: 'ready' },
    ],
    issues: [],
    canEdit: true,
    ...overrides,
  }
}

function testRun(overrides: Record<string, unknown> = {}) {
  return {
    id: 'r1',
    projectId: 'p1',
    testCaseId: 'c1',
    testCaseKey: 'TC-1',
    testCaseTitle: 'Login válido',
    testPlanId: 'tp1',
    testPlanName: 'Regressão 1.0',
    result: 'fail',
    environment: 'staging',
    executedBy: qa,
    executedAt: '2026-01-03T10:00:00Z',
    bugCount: 0,
    evidenceCount: 0,
    version: 1,
    actualResult: 'Erro 500',
    notes: '',
    bugs: [],
    createdAt: '2026-01-03T10:00:00Z',
    updatedAt: '2026-01-03T10:00:00Z',
    canEdit: true,
    canAddEvidence: true,
    canCreateBug: true,
    ...overrides,
  }
}

const baseHandlers = (user: typeof qaUser | typeof readerUser) => ({
  ...csrfHandler,
  'GET /api/users/me': () => jsonResponse(user),
  'GET /api/projects/p1': () => jsonResponse(testProject()),
})

describe('execuções de testes', () => {
  it('lista execuções e filtra por resultado e pelas minhas', async () => {
    mockApi({
      ...baseHandlers(qaUser),
      'GET /api/test-runs?projectId=p1&page=1&pageSize=25': () =>
        jsonResponse(pageOf([testRun({ bugCount: 1, evidenceCount: 2 })])),
      'GET /api/test-runs?projectId=p1&result=pass&page=1&pageSize=25': () =>
        jsonResponse(pageOf([])),
      'GET /api/test-runs?projectId=p1&result=pass&executedBy=me&page=1&pageSize=25': () =>
        jsonResponse(pageOf([testRun({ id: 'r2', result: 'pass' })])),
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/tests/runs')

    const row = (await screen.findByText('Regressão 1.0')).closest('tr')!
    expect(within(row).getByText('Falhou')).toBeInTheDocument()
    expect(within(row).getByText('Quitéria')).toBeInTheDocument()
    expect(within(row).getByRole('link')).toHaveAttribute('href', '/projects/p1/tests/runs/r1')
    expect(screen.getByRole('link', { name: 'Execuções' })).toHaveAttribute(
      'href',
      '/projects/p1/tests/runs',
    )

    await user.selectOptions(screen.getByLabelText('Resultado'), 'pass')
    expect(await screen.findByText('Nenhuma execução encontrada.')).toBeInTheDocument()
    await user.click(screen.getByLabelText('Só as minhas'))
    expect(await screen.findByText('Passou', { selector: 'span' })).toBeInTheDocument()
  })

  it('regista uma execução a partir do plano', async () => {
    const bodies: unknown[] = []
    mockApi({
      ...baseHandlers(qaUser),
      'GET /api/test-cases/c1': () => jsonResponse(testCase()),
      'GET /api/test-plans/tp1': () => jsonResponse(testPlan()),
      'POST /api/test-runs': (init) => {
        bodies.push(JSON.parse(String(init.body)))
        return jsonResponse(testRun(), 201)
      },
      'GET /api/test-runs/r1': () => jsonResponse(testRun()),
      'GET /api/test-runs/r1/evidences': () => jsonResponse([]),
    })
    const user = userEvent.setup()
    const { router } = renderRoutes(
      routes,
      '/projects/p1/tests/runs/new?testCaseId=c1&testPlanId=tp1',
    )

    expect(await screen.findByText('Executar TC-1 · Login válido')).toBeInTheDocument()
    expect(screen.getByText(/Entrar/)).toBeInTheDocument()
    expect(await screen.findByText('Plano: Regressão 1.0')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Resultado'), 'fail')
    await user.type(screen.getByLabelText('Resultado obtido'), 'Erro 500')
    await user.type(screen.getByLabelText('Ambiente'), 'staging')
    await user.click(screen.getByRole('button', { name: 'Registar execução' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/projects/p1/tests/runs/r1'))
    expect(bodies[0]).toEqual({
      testCaseId: 'c1',
      testPlanId: 'tp1',
      result: 'fail',
      actualResult: 'Erro 500',
      environment: 'staging',
      notes: '',
    })
  })

  it('cria um bug a partir de uma execução falhada e mostra evidências', async () => {
    const bugBodies: unknown[] = []
    mockApi({
      ...baseHandlers(qaUser),
      'GET /api/test-runs/r1': () => jsonResponse(testRun({ evidenceCount: 1 })),
      'GET /api/test-runs/r1/evidences': () =>
        jsonResponse([
          {
            id: 'e1',
            testRunId: 'r1',
            originalName: 'ecra.png',
            contentType: 'image/png',
            size: 2048,
            sha256: 'x',
            isImage: true,
            uploadedBy: qa,
            createdAt: '2026-01-03T10:05:00Z',
            canDelete: true,
          },
        ]),
      'POST /api/test-runs/r1/bugs': (init) => {
        bugBodies.push(JSON.parse(String(init.body)))
        return jsonResponse(
          testRun({
            version: 2,
            bugCount: 1,
            bugs: [{ id: 'b1', key: 'DVC-9', title: 'Login devolve 500', type: 'bug', status: 'todo' }],
          }),
          201,
        )
      },
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/tests/runs/r1')

    expect(await screen.findByLabelText('Resultado obtido')).toHaveValue('Erro 500')
    const evidence = await screen.findByRole('link', { name: 'ecra.png' })
    expect(evidence).toHaveAttribute('href', '/api/test-runs/r1/evidences/e1/content')
    expect(screen.getByLabelText('Adicionar evidência')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Título do bug (opcional)'), 'Login devolve 500')
    await user.click(screen.getByRole('button', { name: 'Criar bug' }))
    const bug = await screen.findByRole('link', { name: 'DVC-9 · Login devolve 500' })
    expect(bug).toHaveAttribute('href', '/issues/DVC-9')
    expect(bugBodies).toEqual([{ title: 'Login devolve 500' }])
  })

  it('mostra a execução só para consulta sem permissões', async () => {
    mockApi({
      ...baseHandlers(readerUser),
      'GET /api/test-runs/r1': () =>
        jsonResponse(
          testRun({ canEdit: false, canAddEvidence: false, canCreateBug: false, result: 'pass' }),
        ),
      'GET /api/test-runs/r1/evidences': () => jsonResponse([]),
    })
    renderRoutes(routes, '/projects/p1/tests/runs/r1')

    expect(await screen.findByLabelText('Resultado')).toBeDisabled()
    expect(screen.getByText(/Consulta apenas/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Guardar alterações' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Criar bug' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Adicionar evidência')).not.toBeInTheDocument()
  })

  it('mostra o progresso do plano com regressões e ação de executar', async () => {
    mockApi({
      ...baseHandlers(qaUser),
      'GET /api/test-plans/tp1': () => jsonResponse(testPlan()),
      'GET /api/test-cases?projectId=p1&status=draft&status=ready&pageSize=100': () =>
        jsonResponse(pageOf([], 1, 100)),
      'GET /api/issues?projectId=p1&sort=number&pageSize=100': () => jsonResponse(pageOf([])),
      'GET /api/test-plans/tp1/progress': () =>
        jsonResponse({
          testPlanId: 'tp1',
          totalCases: 2,
          counts: { pass: 0, fail: 1, blocked: 0, not_run: 1, skipped: 0 },
          executedCases: 1,
          passRate: 0,
          regressions: 1,
          cases: [
            {
              testCase: testPlan().testCases[0],
              lastRunId: 'r1',
              lastResult: 'fail',
              lastExecutedAt: '2026-01-03T10:00:00Z',
              lastExecutedBy: qa,
              previousResult: 'pass',
              regression: true,
            },
            {
              testCase: testPlan().testCases[1],
              lastRunId: null,
              lastResult: 'not_run',
              lastExecutedAt: null,
              lastExecutedBy: null,
              previousResult: null,
              regression: false,
            },
          ],
        }),
    })
    renderRoutes(routes, '/projects/p1/tests/plans/tp1')

    expect(await screen.findByText('Regressão', { selector: 'span' })).toBeInTheDocument()
    expect(screen.getByText('1/2')).toBeInTheDocument()
    expect(screen.getByText('0%')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Executar TC-2' })).toHaveAttribute(
      'href',
      '/projects/p1/tests/runs/new?testCaseId=c2&testPlanId=tp1',
    )
    expect(screen.getByRole('link', { name: 'Histórico de execuções' })).toHaveAttribute(
      'href',
      '/projects/p1/tests/runs?testPlanId=tp1',
    )
  })
})
