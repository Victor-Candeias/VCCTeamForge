import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { routes } from '@/app/router'
import {
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

function summary(number: number, overrides: Record<string, unknown> = {}) {
  return {
    id: `i${number}`,
    projectId: 'p1',
    key: `APP-${number}`,
    number,
    type: 'story',
    title: `Issue ${number}`,
    status: 'todo',
    priority: 'medium',
    assignee: null,
    storyPoints: null,
    labels: [],
    blocked: false,
    dueDate: null,
    parentIssueId: null,
    sprintId: null,
    updatedAt: '2026-01-02T10:00:00Z',
    version: 1,
    ...overrides,
  }
}

const base = {
  'GET /api/users/me': () => jsonResponse(techLeadUser),
  'GET /api/projects/p1': () => jsonResponse(testProject()),
  'GET /api/projects/p1/members': () => jsonResponse(members),
  'GET /api/projects/p1/labels': () => jsonResponse(['auth', 'ui']),
}

const list = (query: string) => `GET /api/issues?projectId=p1&${query}`

describe('pesquisa de issues', () => {
  it('aplica os filtros do URL ao pedido e aos controlos', async () => {
    mockApi({
      ...base,
      [list('status=in_progress&assigneeId=me&label=auth&blocked=true&sort=priority&page=2&pageSize=25')]:
        () => jsonResponse({ ...pageOf([summary(7)]), page: 2, total: 26 }),
    })
    renderRoutes(
      routes,
      '/projects/p1/issues?status=in_progress&assigneeId=me&label=auth&blocked=true&sort=priority&page=2',
    )

    expect(await screen.findByRole('link', { name: 'APP-7' })).toBeInTheDocument()
    expect(screen.getByLabelText('Estado')).toHaveValue('in_progress')
    expect(screen.getByLabelText('Responsável')).toHaveValue('me')
    expect(screen.getByLabelText('Só bloqueadas')).toBeChecked()
    expect(screen.getByText('Página 2 de 2')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /Prioridade/ })).toHaveAttribute(
      'aria-sort',
      'ascending',
    )
    await waitFor(() => expect(screen.getByLabelText('Label')).toHaveValue('auth'))
  })

  it('altera filtros, volta à página 1 e atualiza o URL', async () => {
    mockApi({
      ...base,
      [list('page=2&pageSize=25')]: () =>
        jsonResponse({ ...pageOf([summary(1)]), page: 2, total: 30 }),
      [list('type=bug&page=1&pageSize=25')]: () =>
        jsonResponse(pageOf([summary(3, { type: 'bug', title: 'Um bug' })])),
    })
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, '/projects/p1/issues?page=2')

    await screen.findByRole('link', { name: 'APP-1' })
    await user.selectOptions(screen.getByLabelText('Tipo'), 'bug')

    expect(await screen.findByRole('link', { name: 'Um bug' })).toBeInTheDocument()
    expect(router.state.location.search).toBe('?type=bug')
  })

  it('pesquisa com debounce e limpa os filtros', async () => {
    const fetchMock = mockApi({
      ...base,
      [list('page=1&pageSize=25')]: () => jsonResponse(pageOf([summary(1), summary(2)])),
      [list('q=APP-2&page=1&pageSize=25')]: () => jsonResponse(pageOf([summary(2)])),
    })
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, '/projects/p1/issues')

    await screen.findByRole('link', { name: 'APP-1' })
    await user.type(screen.getByLabelText('Pesquisar'), 'APP-2')

    await waitFor(() => expect(router.state.location.search).toBe('?q=APP-2'))
    await waitFor(() =>
      expect(screen.queryByRole('link', { name: 'APP-1' })).not.toBeInTheDocument(),
    )
    const searches = fetchMock.mock.calls.filter(([url]) => String(url).includes('q='))
    expect(searches).toHaveLength(1)

    await user.click(screen.getByRole('button', { name: 'Limpar filtros (1)' }))
    expect(await screen.findByRole('link', { name: 'APP-1' })).toBeInTheDocument()
    expect(screen.getByLabelText('Pesquisar')).toHaveValue('')
  })

  it('ordena pelo cabeçalho e muda de página', async () => {
    mockApi({
      ...base,
      [list('page=1&pageSize=25')]: () =>
        jsonResponse({ ...pageOf([summary(2), summary(1)]), total: 30 }),
      [list('sort=title&page=1&pageSize=25')]: () =>
        jsonResponse({ ...pageOf([summary(1), summary(2)]), total: 30 }),
      [list('sort=-title&page=1&pageSize=25')]: () =>
        jsonResponse({ ...pageOf([summary(2), summary(1)]), total: 30 }),
      [list('sort=-title&page=2&pageSize=25')]: () =>
        jsonResponse({ ...pageOf([summary(9)]), page: 2, total: 30 }),
    })
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, '/projects/p1/issues')

    await screen.findByRole('link', { name: 'APP-1' })
    const header = screen.getByRole('columnheader', { name: /Título/ })
    expect(header).toHaveAttribute('aria-sort', 'none')
    await user.click(within(header).getByRole('button'))
    await waitFor(() => expect(header).toHaveAttribute('aria-sort', 'ascending'))
    await user.click(within(header).getByRole('button'))
    await waitFor(() => expect(header).toHaveAttribute('aria-sort', 'descending'))

    await user.click(screen.getByRole('button', { name: 'Seguinte' }))
    expect(await screen.findByRole('link', { name: 'APP-9' })).toBeInTheDocument()
    expect(router.state.location.search).toBe('?sort=-title&page=2')
  })
})
