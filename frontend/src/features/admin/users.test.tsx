import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { routes } from '@/app/router'
import { csrfHandler, jsonResponse, mockApi, pageOf, renderRoutes, testUser } from '@/test/utils'

const admin = {
  id: 'a1',
  email: 'admin@exemplo.pt',
  name: 'Admin',
  role: 'admin' as const,
  permissions: ['users:manage', 'audit:read', 'projects:read'],
}

function managedUser(overrides: Record<string, unknown> = {}) {
  return {
    id: 'u1',
    email: 'diana@exemplo.pt',
    name: 'Diana',
    role: 'developer',
    status: 'active',
    lastLoginAt: null,
    passwordChangedAt: '2026-01-01T10:00:00Z',
    createdAt: '2026-01-01T10:00:00Z',
    updatedAt: '2026-01-01T10:00:00Z',
    version: 1,
    ...overrides,
  }
}

const LIST = 'GET /api/admin/users?page=1&pageSize=25'

describe('gestão de utilizadores', () => {
  it('mostra a navegação e a lista só a quem tem users:manage', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(admin),
      [LIST]: () =>
        jsonResponse(pageOf([managedUser(), managedUser({ id: 'a1', name: 'Admin' })])),
    })
    renderRoutes(routes, '/admin/users')

    const row = (await screen.findByRole('link', { name: 'Diana' })).closest('tr')!
    expect(within(row).getByText('Ativo')).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: 'Desativar' })).toBeInTheDocument()
    const ownRow = screen.getByRole('link', { name: 'Admin' }).closest('tr')!
    expect(within(ownRow).queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Utilizadores' })).toHaveAttribute(
      'href',
      '/admin/users',
    )
  })

  it('recusa o acesso sem permissão', async () => {
    mockApi({ 'GET /api/users/me': () => jsonResponse(testUser) })
    renderRoutes(routes, '/admin/users')

    expect(await screen.findByText(/não tem permissão para gerir/i)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Utilizadores' })).not.toBeInTheDocument()
  })

  it('desativa um utilizador após confirmação', async () => {
    const bodies: unknown[] = []
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(admin),
      [LIST]: () => jsonResponse(pageOf([managedUser()])),
      'PATCH /api/admin/users/u1': (init) => {
        bodies.push(JSON.parse(String(init.body)))
        return jsonResponse(managedUser({ status: 'disabled', version: 2 }))
      },
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const user = userEvent.setup()
    renderRoutes(routes, '/admin/users')

    await user.click(await screen.findByRole('button', { name: 'Desativar' }))

    await waitFor(() => expect(bodies).toEqual([{ version: 1, status: 'disabled' }]))
  })

  it('valida e cria um utilizador', async () => {
    const bodies: unknown[] = []
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(admin),
      [LIST]: () => jsonResponse(pageOf([])),
      'POST /api/admin/users': (init) => {
        bodies.push(JSON.parse(String(init.body)))
        return jsonResponse(managedUser({ id: 'u9', name: 'Nova' }), 201)
      },
    })
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, '/admin/users/new')

    await user.type(await screen.findByLabelText('Nome'), 'Nova')
    await user.type(screen.getByLabelText('Email'), 'nova@exemplo.pt')
    await user.selectOptions(screen.getByLabelText('Perfil'), 'qa')
    await user.type(screen.getByLabelText('Password'), 'curta')
    await user.type(screen.getByLabelText('Confirmar password'), 'outra')
    await user.click(screen.getByRole('button', { name: 'Criar utilizador' }))

    expect(await screen.findByText('Mínimo 12 caracteres')).toBeInTheDocument()
    expect(screen.getByText('As passwords não coincidem')).toBeInTheDocument()
    expect(bodies).toHaveLength(0)

    await user.clear(screen.getByLabelText('Password'))
    await user.type(screen.getByLabelText('Password'), 'uma-password-segura')
    await user.clear(screen.getByLabelText('Confirmar password'))
    await user.type(screen.getByLabelText('Confirmar password'), 'uma-password-segura')
    await user.click(screen.getByRole('button', { name: 'Criar utilizador' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/admin/users'))
    expect(bodies[0]).toEqual({
      name: 'Nova',
      email: 'nova@exemplo.pt',
      role: 'qa',
      password: 'uma-password-segura',
    })
  })

  it('mostra o erro do servidor no campo email', async () => {
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(admin),
      'POST /api/admin/users': () =>
        jsonResponse(
          { title: 'Conflito', detail: 'Já existe um utilizador com este email', field: 'email' },
          409,
        ),
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/admin/users/new')

    await user.type(await screen.findByLabelText('Nome'), 'Nova')
    await user.type(screen.getByLabelText('Email'), 'diana@exemplo.pt')
    await user.type(screen.getByLabelText('Password'), 'uma-password-segura')
    await user.type(screen.getByLabelText('Confirmar password'), 'uma-password-segura')
    await user.click(screen.getByRole('button', { name: 'Criar utilizador' }))

    const messages = await screen.findAllByText('Já existe um utilizador com este email')
    expect(messages.length).toBeGreaterThan(0)
  })

  it('bloqueia perfil e estado na própria conta e redefine a password', async () => {
    const bodies: unknown[] = []
    mockApi({
      ...csrfHandler,
      'GET /api/users/me': () => jsonResponse(admin),
      'GET /api/admin/users/a1': () =>
        jsonResponse(managedUser({ id: 'a1', name: 'Admin', role: 'admin', version: 4 })),
      'POST /api/admin/users/a1/password': (init) => {
        bodies.push(JSON.parse(String(init.body)))
        return jsonResponse(managedUser({ id: 'a1', name: 'Admin', role: 'admin', version: 5 }))
      },
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/admin/users/a1')

    expect(await screen.findByLabelText('Perfil')).toBeDisabled()
    expect(screen.getByLabelText('Estado')).toBeDisabled()

    await user.type(screen.getByLabelText('Nova password'), 'nova-password-segura')
    await user.type(screen.getByLabelText('Confirmar nova password'), 'nova-password-segura')
    await user.click(screen.getByRole('button', { name: 'Redefinir password' }))

    expect(await screen.findByText('Password redefinida.')).toBeInTheDocument()
    expect(bodies).toEqual([{ version: 4, password: 'nova-password-segura' }])
  })
})
