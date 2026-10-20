import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

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
  members: [
    { id: 'tl1', name: 'Tiago', email: 'tiago@exemplo.pt', role: 'tech_lead', isLead: true },
    { id: 'd1', name: 'Diana', email: 'diana@exemplo.pt', role: 'developer', isLead: false },
  ],
}

describe('lista de projetos', () => {
  it('mostra projetos e o botão de criação só com projects:manage', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(techLeadUser),
      'GET /api/projects?page=1&pageSize=25': () => jsonResponse(pageOf([testProject()])),
    })
    renderRoutes(routes, '/projects')

    expect(await screen.findByRole('link', { name: 'Aplicação' })).toHaveAttribute(
      'href',
      '/projects/p1',
    )
    expect(screen.getByRole('link', { name: 'Novo projeto' })).toBeInTheDocument()
  })

  it('esconde ações de gestão e mostra estado vazio', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(testUser),
      'GET /api/projects?page=1&pageSize=25': () => jsonResponse(pageOf([])),
    })
    renderRoutes(routes, '/projects')

    expect(await screen.findByText('Nenhum projeto encontrado.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Novo projeto' })).not.toBeInTheDocument()
  })

  it('indica erro ao carregar', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(testUser),
      'GET /api/projects?page=1&pageSize=25': () => jsonResponse({ title: 'Erro' }, 500),
    })
    renderRoutes(routes, '/projects')

    expect(await screen.findByText('Não foi possível carregar os projetos.')).toBeInTheDocument()
  })
})

describe('formulário de projeto', () => {
  it('valida a chave e as datas antes de enviar', async () => {
    const fetchMock = mockApi({
      'GET /api/users/me': () => jsonResponse(techLeadUser),
      'GET /api/users?limit=20': () => jsonResponse([]),
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/new')

    await user.type(await screen.findByLabelText('Chave'), '1x')
    await user.type(screen.getByLabelText('Nome'), 'Novo')
    await user.type(screen.getByLabelText('Data de início'), '2026-03-10')
    await user.type(screen.getByLabelText('Data alvo'), '2026-03-01')
    await user.click(screen.getByRole('button', { name: 'Criar projeto' }))

    expect(await screen.findByText(/a começar por letra/)).toBeInTheDocument()
    expect(screen.getByText(/não pode ser anterior/)).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith('/api/projects', expect.anything())
  })

  it('cria o projeto e abre o detalhe', async () => {
    const createdBodies: unknown[] = []
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(techLeadUser),
      'GET /api/users?limit=20': () => jsonResponse([]),
      'POST /api/projects': (init) => {
        createdBodies.push(JSON.parse(String(init.body)))
        return jsonResponse(testProject({ id: 'p9', key: 'NOVO', name: 'Novo' }), 201)
      },
      'GET /api/projects/p9': () => jsonResponse(testProject({ id: 'p9', key: 'NOVO' })),
    })
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, '/projects/new')

    await user.type(await screen.findByLabelText('Chave'), 'novo')
    await user.type(screen.getByLabelText('Nome'), 'Novo')
    await user.click(screen.getByRole('button', { name: 'Criar projeto' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/projects/p9'))
    expect(createdBodies[0]).toMatchObject({ key: 'NOVO', name: 'Novo', leadUserId: null })
  })

  it('mostra aviso de conflito ao editar uma versão desatualizada', async () => {
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(techLeadUser),
      'GET /api/users?limit=20': () => jsonResponse([]),
      'GET /api/projects/p1': () => jsonResponse(testProject()),
      'PATCH /api/projects/p1': () =>
        jsonResponse({ title: 'Conflito', detail: 'Versão desatualizada', currentVersion: 4 }, 409),
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/edit')

    const name = await screen.findByLabelText('Nome')
    expect(screen.getByLabelText('Chave')).toBeDisabled()
    await user.clear(name)
    await user.type(name, 'Outro nome')
    await user.click(screen.getByRole('button', { name: 'Guardar alterações' }))

    expect(await screen.findByText(/alterados por outra pessoa/)).toBeInTheDocument()
  })
})

describe('detalhe e membros', () => {
  it('mostra separadores e o resumo', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(testUser),
      'GET /api/projects/p1': () => jsonResponse(testProject({ canManage: false })),
    })
    renderRoutes(routes, '/projects/p1')

    expect(await screen.findByRole('heading', { name: 'Aplicação' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Membros' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sprints' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Testes' })).toBeInTheDocument()
    expect(screen.getByText('Releases')).toHaveAttribute('aria-disabled', 'true')
    expect(screen.queryByRole('button', { name: 'Arquivar' })).not.toBeInTheDocument()
  })

  it('adiciona e remove membros, sem remover o responsável', async () => {
    const calls: string[] = []
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(techLeadUser),
      'GET /api/projects/p1': () => jsonResponse(testProject()),
      'GET /api/projects/p1/members': () => jsonResponse(members),
      'GET /api/users?limit=20': () =>
        jsonResponse([
          { id: 'q1', name: 'Quim', email: 'quim@exemplo.pt', role: 'qa' },
          { id: 'd1', name: 'Diana', email: 'diana@exemplo.pt', role: 'developer' },
        ]),
      'POST /api/projects/p1/members': (init) => {
        calls.push(`add ${String(init.body)}`)
        return jsonResponse({
          ...members,
          version: 4,
          members: [
            ...members.members,
            { id: 'q1', name: 'Quim', email: 'quim@exemplo.pt', role: 'qa', isLead: false },
          ],
        })
      },
      'DELETE /api/projects/p1/members/d1?version=3': () => {
        calls.push('remove d1')
        return jsonResponse({ ...members, members: [members.members[0]] })
      },
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1/members')

    const table = await screen.findByRole('table')
    const leadRow = within(table).getByText('Tiago').closest('tr')!
    expect(within(leadRow).queryByRole('button')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Remover Diana' }))
    await waitFor(() => expect(calls).toContain('remove d1'))

    const select = screen.getByLabelText('Utilizador')
    await waitFor(() => expect(within(select).getByText(/Quim/)).toBeInTheDocument())
    await user.selectOptions(select, 'q1')
    await user.click(screen.getByRole('button', { name: 'Adicionar membro' }))
    await waitFor(() => expect(calls).toContain('add {"userId":"q1","version":3}'))
  })

  it('arquiva após confirmação', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const archiveMock = vi.fn(() => jsonResponse(testProject({ status: 'archived', version: 4 })))
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(techLeadUser),
      'GET /api/projects/p1': () => jsonResponse(testProject()),
      'POST /api/projects/p1/archive': archiveMock,
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/projects/p1')

    await user.click(await screen.findByRole('button', { name: 'Arquivar' }))

    expect(await screen.findByText('Projeto arquivado: apenas leitura.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Restaurar' })).toBeInTheDocument()
  })
})
