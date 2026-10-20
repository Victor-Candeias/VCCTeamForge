import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { routes } from '@/app/router'
import { reorder } from '@/features/issues/ordering'
import {
  csrfHandler,
  jsonResponse,
  mockApi,
  pageOf,
  renderRoutes,
  techLeadUser,
  testProject,
} from '@/test/utils'

const projectHandlers = {
  'GET /api/users/me': () => jsonResponse(techLeadUser),
  'GET /api/projects/p1': () => jsonResponse(testProject()),
}

function summary(id: string, overrides: Record<string, unknown> = {}) {
  const number = Number(id.slice(1))
  return {
    id,
    projectId: 'p1',
    key: `APP-${number}`,
    number,
    type: 'task',
    title: `Tarefa ${number}`,
    status: 'todo',
    priority: 'medium',
    assignee: null,
    storyPoints: null,
    labels: [],
    blocked: false,
    dueDate: null,
    parentIssueId: null,
    sprintId: null,
    rank: number * 1024,
    updatedAt: '2026-01-02T10:00:00Z',
    version: 1,
    ...overrides,
  }
}

function boardOf(...issues: ReturnType<typeof summary>[]) {
  return {
    columnLimit: 200,
    doneWindowDays: 14,
    columns: ['todo', 'in_progress', 'code_review', 'testing', 'done'].map((status) => {
      const items = issues.filter((issue) => issue.status === status)
      return { status, items, total: items.length, truncated: false }
    }),
  }
}

const boardKey = 'GET /api/projects/p1/board'
const backlogKey =
  'GET /api/issues?projectId=p1&sprintId=none&status=todo&status=in_progress' +
  '&status=code_review&status=testing&sort=rank&pageSize=100'

describe('quadro Kanban', () => {
  it('move uma issue pelo menu "Mover para" e mostra impedimentos', async () => {
    let issue = summary('i1')
    let body: Record<string, unknown> = {}
    mockApi({
      ...projectHandlers,
      ...csrfHandler,
      [boardKey]: () => jsonResponse(boardOf(issue, summary('i2', { blocked: true }))),
      'PATCH /api/issues/i1': (init) => {
        body = JSON.parse(String(init.body))
        issue = summary('i1', { status: 'in_progress', version: 2 })
        return jsonResponse({ ...issue, canEdit: true })
      },
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/board')

    const todo = await screen.findByRole('region', { name: 'To Do' })
    expect(within(todo).getByText('Bloqueada')).toBeInTheDocument()
    const menu = within(todo).getByLabelText('Mover APP-1 para')
    expect(
      within(menu)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual(['Mover para…', 'Em progresso'])
    await user.selectOptions(menu, 'in_progress')

    const progress = screen.getByRole('region', { name: 'Em progresso' })
    expect(await within(progress).findByText('Tarefa 1')).toBeInTheDocument()
    expect(body).toEqual({ status: 'in_progress', version: 1 })
    await waitFor(() => expect(within(progress).getByLabelText('Mover APP-1 para')).toBeEnabled())
    expect(within(todo).queryByText('Tarefa 1')).not.toBeInTheDocument()
  })

  it('reverte a mudança e mostra a mensagem quando a API devolve 422', async () => {
    mockApi({
      ...projectHandlers,
      ...csrfHandler,
      [boardKey]: () => jsonResponse(boardOf(summary('i1', { status: 'in_progress' }))),
      'PATCH /api/issues/i1': () =>
        jsonResponse({ title: 'Regra', status: 422, detail: 'Transição inválida' }, 422),
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/board')

    const progress = await screen.findByRole('region', { name: 'Em progresso' })
    await user.selectOptions(within(progress).getByLabelText('Mover APP-1 para'), 'done')

    expect(await screen.findByText('Transição inválida')).toBeInTheDocument()
    await waitFor(() => expect(within(progress).getByText('Tarefa 1')).toBeInTheDocument())
    const done = screen.getByRole('region', { name: 'Concluída' })
    expect(within(done).queryByText('Tarefa 1')).not.toBeInTheDocument()
  })

  it('não envia pedidos ao largar numa coluna com transição não permitida', async () => {
    const fetchMock = mockApi({
      ...projectHandlers,
      [boardKey]: () => jsonResponse(boardOf(summary('i1'))),
    })
    renderRoutes(routes, '/projects/p1/board')

    const card = await screen.findByRole('article', { name: 'APP-1 Tarefa 1' })
    fireEvent.dragStart(card)
    fireEvent.drop(screen.getByRole('region', { name: 'Concluída' }))

    expect(
      await screen.findByText('Transição não permitida: To Do → Concluída.'),
    ).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith('/api/issues/i1', expect.anything())
  })
})

describe('backlog', () => {
  it('reordena com o botão Subir e envia os vizinhos à API', async () => {
    let order = ['i1', 'i2', 'i3']
    let body: Record<string, unknown> = {}
    mockApi({
      ...projectHandlers,
      ...csrfHandler,
      [backlogKey]: () =>
        jsonResponse(
          pageOf(
            order.map((id) => summary(id)),
            1,
            100,
          ),
        ),
      'POST /api/issues/i3/rank': (init) => {
        body = JSON.parse(String(init.body))
        order = ['i1', 'i3', 'i2']
        return jsonResponse(summary('i3', { rank: 1536, version: 2 }))
      },
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/backlog')

    expect(await screen.findByText('Tarefa 3')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Subir APP-1' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Subir APP-3' }))

    const titles = () =>
      within(screen.getByRole('list', { name: 'Backlog' }))
        .getAllByRole('article')
        .map((card) => card.getAttribute('aria-label'))
    await waitFor(() =>
      expect(titles()).toEqual(['APP-1 Tarefa 1', 'APP-3 Tarefa 3', 'APP-2 Tarefa 2']),
    )
    expect(body).toEqual({ version: 1, afterId: 'i1', beforeId: 'i2' })
  })

  it('calcula a nova ordem e os vizinhos', () => {
    expect(reorder(['a', 'b', 'c'], 'c', 0)).toEqual({
      order: ['c', 'a', 'b'],
      afterId: undefined,
      beforeId: 'a',
    })
    expect(reorder(['a', 'b', 'c'], 'a', 2)).toEqual({
      order: ['b', 'c', 'a'],
      afterId: 'c',
      beforeId: undefined,
    })
    expect(reorder(['a', 'b'], 'a', 0)).toBeNull()
  })
})
