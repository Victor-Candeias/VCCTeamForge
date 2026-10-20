import { screen, waitFor } from '@testing-library/react'
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
} from '@/test/utils'

const members = {
  version: 3,
  canManage: true,
  members: [{ id: 'tl1', name: 'Tiago', email: 'tiago@exemplo.pt', role: 'tech_lead', isLead: true }],
}

function testIssue(overrides: Record<string, unknown> = {}) {
  return {
    id: 'i1',
    projectId: 'p1',
    projectKey: 'APP',
    key: 'APP-1',
    number: 1,
    type: 'story',
    title: 'Login com SSO',
    status: 'todo',
    priority: 'medium',
    assignee: null,
    reporter: { id: 'tl1', name: 'Tiago', email: 'tiago@exemplo.pt', role: 'tech_lead' },
    storyPoints: 3,
    labels: ['auth'],
    blocked: false,
    blockReason: null,
    blockedAt: null,
    dueDate: null,
    parentIssueId: null,
    parent: null,
    sprintId: null,
    description: '**Importante**',
    acceptanceCriteria: ['Entra com SSO'],
    dependsOn: [],
    completedAt: null,
    createdAt: '2026-01-01T10:00:00Z',
    updatedAt: '2026-01-02T10:00:00Z',
    version: 1,
    canEdit: true,
    allowedTransitions: ['in_progress'],
    ...overrides,
  }
}

const projectHandlers = {
  'GET /api/users/me': () => jsonResponse(techLeadUser),
  'GET /api/projects/p1': () => jsonResponse(testProject()),
  'GET /api/projects/p1/members': () => jsonResponse(members),
}

describe('lista de issues', () => {
  it('mostra as issues do projeto com ligação ao detalhe', async () => {
    mockApi({
      ...projectHandlers,
      'GET /api/issues?projectId=p1&page=1&pageSize=25': () => jsonResponse(pageOf([testIssue()])),
    })
    renderRoutes(routes, '/projects/p1/issues')

    expect(await screen.findByRole('link', { name: 'APP-1' })).toHaveAttribute(
      'href',
      '/issues/APP-1',
    )
    expect(screen.getByRole('link', { name: 'Nova issue' })).toBeInTheDocument()
  })
})

describe('formulário de issue', () => {
  it('exige pai numa subtarefa e valida story points', async () => {
    const fetchMock = mockApi({
      ...projectHandlers,
      'GET /api/issues?projectId=p1&pageSize=100': () => jsonResponse(pageOf([])),
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/issues/new')

    await user.selectOptions(await screen.findByLabelText('Tipo'), 'subtask')
    await user.type(screen.getByLabelText('Título'), 'Sub')
    await user.type(screen.getByLabelText('Story points'), '0.3')
    await user.click(screen.getByRole('button', { name: 'Criar issue' }))

    expect(await screen.findByText('Uma subtarefa tem de ter uma issue pai')).toBeInTheDocument()
    expect(screen.getByText('Entre 0 e 100, em múltiplos de 0,5')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith('/api/issues', expect.anything())
  })

  it('cria a issue e abre o detalhe', async () => {
    let body: Record<string, unknown> = {}
    mockApi({
      ...projectHandlers,
      ...csrfHandler,
      'GET /api/issues?projectId=p1&pageSize=100': () => jsonResponse(pageOf([])),
      'POST /api/issues': (init) => {
        body = JSON.parse(String(init.body))
        return jsonResponse(testIssue(), 201)
      },
      'GET /api/issues/by-key/APP-1': () => jsonResponse(testIssue()),
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/issues/new')

    await user.type(await screen.findByLabelText('Título'), 'Login com SSO')
    await user.type(screen.getByLabelText('Labels (separadas por vírgula)'), 'Auth, ui')
    await user.type(screen.getByLabelText('Story points'), '3')
    await user.click(screen.getByRole('button', { name: 'Criar issue' }))

    expect(await screen.findByRole('heading', { name: 'Login com SSO' })).toBeInTheDocument()
    expect(body).toMatchObject({
      projectId: 'p1',
      type: 'story',
      labels: ['auth', 'ui'],
      storyPoints: 3,
      parentIssueId: null,
    })
  })
})

describe('detalhe da issue', () => {
  it('mostra descrição em Markdown e só as transições permitidas', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(techLeadUser),
      'GET /api/issues/by-key/APP-1': () => jsonResponse(testIssue()),
    })
    renderRoutes(routes, '/issues/APP-1')

    expect(await screen.findByText('Importante')).toHaveProperty('tagName', 'STRONG')
    expect(screen.getByRole('button', { name: 'Mover para Em progresso' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Mover para Concluída/ })).not.toBeInTheDocument()
    expect(screen.getByText('Entra com SSO')).toBeInTheDocument()
  })

  it('bloqueia com motivo e envia a versão', async () => {
    let body: Record<string, unknown> = {}
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(techLeadUser),
      'GET /api/issues/by-key/APP-1': () => jsonResponse(testIssue()),
      'PATCH /api/issues/i1': (init) => {
        body = JSON.parse(String(init.body))
        return jsonResponse(testIssue({ blocked: true, blockReason: 'API externa', version: 2 }))
      },
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/issues/APP-1')

    await user.click(await screen.findByRole('button', { name: 'Bloquear' }))
    await user.type(screen.getByLabelText('Motivo do bloqueio'), 'API externa')
    await user.click(screen.getByRole('button', { name: 'Confirmar bloqueio' }))

    expect(await screen.findByRole('button', { name: 'Desbloquear' })).toBeInTheDocument()
    expect(screen.getByText('API externa')).toBeInTheDocument()
    expect(body).toEqual({ version: 1, blocked: true, blockReason: 'API externa' })
  })

  it('mostra mensagem de conflito quando a versão está desatualizada', async () => {
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(techLeadUser),
      'GET /api/issues/by-key/APP-1': () => jsonResponse(testIssue()),
      'PATCH /api/issues/i1': () =>
        jsonResponse({ title: 'Conflito', status: 409, detail: 'Versão', currentVersion: 2 }, 409),
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/issues/APP-1')

    await user.click(await screen.findByRole('button', { name: 'Mover para Em progresso' }))

    await waitFor(() =>
      expect(screen.getByText(/alterados por outra pessoa/)).toBeInTheDocument(),
    )
  })

  it('esconde ações quando não pode editar', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(techLeadUser),
      'GET /api/issues/by-key/APP-1': () =>
        jsonResponse(testIssue({ canEdit: false, allowedTransitions: [] })),
    })
    renderRoutes(routes, '/issues/APP-1')

    expect(await screen.findByRole('heading', { name: 'Login com SSO' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Bloquear' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Editar' })).not.toBeInTheDocument()
  })
})
