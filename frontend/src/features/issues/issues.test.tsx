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
  testUser,
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

function testComment(overrides: Record<string, unknown> = {}) {
  return {
    id: 'c1',
    issueId: 'i1',
    author: { id: 'tl1', name: 'Tiago', email: 'tiago@exemplo.pt', role: 'tech_lead' },
    body: 'Primeiro **comentário**',
    deleted: false,
    createdAt: '2026-01-03T10:00:00Z',
    editedAt: null,
    deletedAt: null,
    canEdit: true,
    canDelete: true,
    ...overrides,
  }
}

const commentsKey = 'GET /api/issues/i1/comments?page=1&pageSize=50'

describe('comentários e histórico', () => {
  it('cria, edita e remove comentários', async () => {
    let comments = [testComment()]
    const bodies: unknown[] = []
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(techLeadUser),
      'GET /api/issues/by-key/APP-1': () => jsonResponse(testIssue()),
      [commentsKey]: () => jsonResponse(pageOf(comments, 1, 50)),
      'POST /api/issues/i1/comments': (init) => {
        bodies.push(JSON.parse(String(init.body)))
        const created = testComment({ id: 'c2', body: 'Novo texto' })
        comments = [...comments, created]
        return jsonResponse(created, 201)
      },
      'PATCH /api/issues/i1/comments/c1': (init) => {
        bodies.push(JSON.parse(String(init.body)))
        comments = [testComment({ body: 'Texto editado', editedAt: '2026-01-04T10:00:00Z' }), comments[1]]
        return jsonResponse(comments[0])
      },
      'DELETE /api/issues/i1/comments/c2': () => {
        comments = [comments[0], testComment({ id: 'c2', body: null, deleted: true })]
        return new Response(null, { status: 204 })
      },
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/issues/APP-1')

    expect(await screen.findByText('comentário')).toHaveProperty('tagName', 'STRONG')

    await user.type(screen.getByLabelText('Novo comentário (Markdown)'), 'Novo texto')
    await user.click(screen.getByRole('button', { name: 'Comentar' }))
    expect(await screen.findByText('Novo texto')).toBeInTheDocument()
    expect(screen.getByLabelText('Novo comentário (Markdown)')).toHaveValue('')

    await user.click(screen.getAllByRole('button', { name: 'Editar' })[0])
    const editor = screen.getByLabelText('Editar comentário')
    await user.clear(editor)
    await user.type(editor, 'Texto editado')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(await screen.findByText('Texto editado')).toBeInTheDocument()
    expect(screen.getByText('(editado)')).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: 'Remover' })[1])
    await user.click(screen.getByRole('button', { name: 'Confirmar remoção' }))
    expect(await screen.findByText('Comentário removido')).toBeInTheDocument()
    expect(bodies).toEqual([{ body: 'Novo texto' }, { body: 'Texto editado' }])
  })

  it('esconde o formulário sem permissão de comentar', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(testUser),
      'GET /api/issues/by-key/APP-1': () => jsonResponse(testIssue({ canEdit: false })),
      [commentsKey]: () =>
        jsonResponse(pageOf([testComment({ canEdit: false, canDelete: false })], 1, 50)),
    })
    renderRoutes(routes, '/issues/APP-1')

    expect(await screen.findByText('comentário')).toBeInTheDocument()
    expect(screen.queryByLabelText('Novo comentário (Markdown)')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remover' })).not.toBeInTheDocument()
  })

  it('mostra o histórico em linguagem legível', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(techLeadUser),
      'GET /api/issues/by-key/APP-1': () => jsonResponse(testIssue()),
      'GET /api/projects/p1/members': () => jsonResponse(members),
      [commentsKey]: () => jsonResponse(pageOf([], 1, 50)),
      'GET /api/issues/i1/history?page=1&pageSize=25': () =>
        jsonResponse(
          pageOf([
            {
              id: 'h2',
              type: 'updated',
              actor: { id: 'tl1', name: 'Tiago', email: 'tiago@exemplo.pt', role: 'tech_lead' },
              changes: [
                { field: 'status', from: 'todo', to: 'in_progress' },
                { field: 'assigneeId', from: null, to: 'tl1' },
                { field: 'description', from: null, to: null },
              ],
              details: {},
              createdAt: '2026-01-02T10:00:00Z',
            },
            {
              id: 'h1',
              type: 'created',
              actor: { id: 'tl1', name: 'Tiago', email: 'tiago@exemplo.pt', role: 'tech_lead' },
              changes: [],
              details: {},
              createdAt: '2026-01-01T10:00:00Z',
            },
          ]),
        ),
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/issues/APP-1')

    await user.click(await screen.findByRole('tab', { name: 'Histórico' }))

    const statusLine = await screen.findByText(/alterou Estado de/)
    expect(statusLine).toHaveTextContent('alterou Estado de To Do para Em progresso')
    expect(await screen.findByText(/alterou Responsável de/)).toHaveTextContent(
      'alterou Responsável de — para Tiago',
    )
    expect(screen.getByText('alterou Descrição')).toBeInTheDocument()
    expect(screen.getByText('criou a issue')).toBeInTheDocument()
  })
})

describe('auditoria', () => {
  it('lista registos e filtra por ação', async () => {
    const admin = { ...techLeadUser, role: 'admin' as const, permissions: ['audit:read'] }
    const log = {
      id: 'a1',
      action: 'issue.updated',
      actor: { id: 'tl1', name: 'Tiago', email: 'tiago@exemplo.pt', role: 'tech_lead' },
      entityType: 'issue',
      entityId: 'i1',
      ip: null,
      requestId: null,
      details: { issueKey: 'APP-1', changes: [{ field: 'status', from: 'todo', to: 'done' }] },
      createdAt: '2026-01-02T10:00:00Z',
    }
    const fetchMock = mockApi({
      'GET /api/users/me': () => jsonResponse(admin),
      'GET /api/audit-logs?page=1&pageSize=25': () => jsonResponse(pageOf([log])),
      'GET /api/audit-logs?action=x&page=1&pageSize=25': () => jsonResponse(pageOf([])),
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/admin/audit')

    expect(await screen.findByText('APP-1 · campos: status')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Auditoria' })).toBeInTheDocument()

    await user.type(screen.getByLabelText('Ação'), 'x')
    expect(await screen.findByText('Sem registos.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/audit-logs?action=x&page=1&pageSize=25',
      expect.anything(),
    )
  })

  it('nega acesso sem audit:read', async () => {
    mockApi({ 'GET /api/users/me': () => jsonResponse(techLeadUser) })
    renderRoutes(routes, '/admin/audit')

    expect(await screen.findByText(/Não tem permissão/)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Auditoria' })).not.toBeInTheDocument()
  })
})

function testAttachment(overrides: Record<string, unknown> = {}) {
  return {
    id: 'a1',
    issueId: 'i1',
    originalName: 'relatório.pdf',
    contentType: 'application/pdf',
    size: 2048,
    sha256: 'abc',
    isImage: false,
    uploadedBy: { id: 'tl1', name: 'Tiago', email: 'tiago@exemplo.pt', role: 'tech_lead' },
    createdAt: '2026-01-03T10:00:00Z',
    canDelete: true,
    ...overrides,
  }
}

describe('anexos', () => {
  it('carrega, lista e remove anexos', async () => {
    let attachments = [testAttachment()]
    let uploaded: FormDataEntryValue | null = null
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(techLeadUser),
      'GET /api/issues/by-key/APP-1': () => jsonResponse(testIssue()),
      [commentsKey]: () => jsonResponse(pageOf([], 1, 50)),
      'GET /api/issues/i1/attachments': () => jsonResponse(attachments),
      'POST /api/issues/i1/attachments': (init) => {
        uploaded = (init.body as FormData).get('file')
        const created = testAttachment({ id: 'a2', originalName: 'notas.txt', size: 5 })
        attachments = [...attachments, created]
        return jsonResponse(created, 201)
      },
      'DELETE /api/attachments/a1': () => {
        attachments = attachments.filter((attachment) => attachment.id !== 'a1')
        return new Response(null, { status: 204 })
      },
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/issues/APP-1')

    const link = await screen.findByRole('link', { name: 'relatório.pdf' })
    expect(link).toHaveAttribute('href', '/api/attachments/a1/content')
    expect(screen.getByText(/2,0 KB/)).toBeInTheDocument()

    const file = new File(['olá!'], 'notas.txt', { type: 'text/plain' })
    await user.upload(screen.getByLabelText('Adicionar anexo'), file)
    expect(await screen.findByRole('link', { name: 'notas.txt' })).toBeInTheDocument()
    expect(uploaded).toBeInstanceOf(File)
    expect((uploaded as unknown as File).name).toBe('notas.txt')

    await user.click(screen.getByRole('button', { name: 'Remover relatório.pdf' }))
    await user.click(screen.getByRole('button', { name: 'Confirmar remoção' }))
    await waitFor(() =>
      expect(screen.queryByRole('link', { name: 'relatório.pdf' })).not.toBeInTheDocument(),
    )
  })

  it('rejeita ficheiros demasiado grandes no cliente e mostra erros do servidor', async () => {
    const fetchMock = mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(techLeadUser),
      'GET /api/issues/by-key/APP-1': () => jsonResponse(testIssue()),
      [commentsKey]: () => jsonResponse(pageOf([], 1, 50)),
      'GET /api/issues/i1/attachments': () => jsonResponse([]),
      'POST /api/issues/i1/attachments': () =>
        jsonResponse(
          { title: 'Regra', status: 422, detail: 'Tipo de ficheiro não permitido', field: 'file' },
          422,
        ),
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/issues/APP-1')

    const input = await screen.findByLabelText('Adicionar anexo')
    const big = new File(['x'], 'grande.pdf', { type: 'application/pdf' })
    Object.defineProperty(big, 'size', { value: 21 * 1024 * 1024 })
    await user.upload(input, big)
    expect(await screen.findByText(/excede o máximo de 20,0 MB/)).toBeInTheDocument()
    const posts = fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')
    expect(posts).toHaveLength(0)

    await user.upload(input, new File(['x'], 'falso.pdf', { type: 'application/pdf' }))
    expect(await screen.findByText('Tipo de ficheiro não permitido')).toBeInTheDocument()
  })

  it('esconde o upload sem issues:write', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(testUser),
      'GET /api/issues/by-key/APP-1': () => jsonResponse(testIssue({ canEdit: false })),
      [commentsKey]: () => jsonResponse(pageOf([], 1, 50)),
      'GET /api/issues/i1/attachments': () => jsonResponse([testAttachment({ canDelete: false })]),
    })
    renderRoutes(routes, '/issues/APP-1')

    expect(await screen.findByRole('link', { name: 'relatório.pdf' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Adicionar anexo')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Remover/ })).not.toBeInTheDocument()
  })
})
