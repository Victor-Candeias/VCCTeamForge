import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { routes } from '@/app/router'
import { safeRedirectPath } from '@/features/auth/useAuth'
import { jsonResponse, mockApi, renderRoutes, testUser } from '@/test/utils'

const unauthenticated = () => jsonResponse({ title: 'Autenticação necessária' }, 401)

describe('autenticação', () => {
  it('redireciona para o login guardando o destino', async () => {
    mockApi({ 'GET /api/users/me': unauthenticated })

    const { router } = renderRoutes(routes, '/projetos?x=1')

    expect(await screen.findByRole('button', { name: 'Entrar' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(router.state.location.search).toBe(`?next=${encodeURIComponent('/projetos?x=1')}`)
  })

  it('inicia sessão com token CSRF e volta ao destino', async () => {
    const fetchMock = mockApi({
      'GET /api/users/me': unauthenticated,
      'GET /api/auth/csrf': () => {
        document.cookie = 'vcctf_csrf=token-csrf; path=/'
        return jsonResponse({ csrfToken: 'token-csrf' })
      },
      'POST /api/auth/login': () => jsonResponse(testUser),
      'GET /api/health': () => jsonResponse({ status: 'ok', version: '0.1.0' }),
    })
    const user = userEvent.setup()
    const { router } = renderRoutes(routes, '/login?next=%2F')

    await user.type(await screen.findByLabelText('Email'), 'ana@exemplo.pt')
    await user.type(screen.getByLabelText('Password'), 'segredo-muito-longo')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByText('Ana')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
    const [, init] = fetchMock.mock.calls.find(([url]) => url === '/api/auth/login')!
    expect(new Headers(init?.headers).get('X-CSRF-Token')).toBe('token-csrf')
    expect(JSON.parse(String(init?.body))).toEqual({
      email: 'ana@exemplo.pt',
      password: 'segredo-muito-longo',
    })
  })

  it('mostra o erro de credenciais inválidas', async () => {
    document.cookie = 'vcctf_csrf=token-csrf; path=/'
    mockApi({
      'GET /api/users/me': unauthenticated,
      'POST /api/auth/login': () =>
        jsonResponse({ title: 'Autenticação necessária', detail: 'Email ou password inválidos' }, 401),
    })
    const user = userEvent.setup()
    renderRoutes(routes, '/login')

    await user.type(await screen.findByLabelText('Email'), 'ana@exemplo.pt')
    await user.type(screen.getByLabelText('Password'), 'errada')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByText('Email ou password inválidos')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toHaveValue('')
  })

  it('valida o formulário antes de contactar a API', async () => {
    const fetchMock = mockApi({ 'GET /api/users/me': unauthenticated })
    const user = userEvent.setup()
    renderRoutes(routes, '/login')

    await user.click(await screen.findByRole('button', { name: 'Entrar' }))

    expect(await screen.findByText('Indique um email válido')).toBeInTheDocument()
    expect(screen.getByText('Indique a password')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith('/api/auth/login', expect.anything())
  })

  it('termina a sessão', async () => {
    document.cookie = 'vcctf_csrf=token-sessao; path=/'
    const fetchMock = mockApi({
      'GET /api/users/me': () => jsonResponse(testUser),
      'GET /api/health': () => jsonResponse({ status: 'ok', version: '0.1.0' }),
      'POST /api/auth/logout': () => new Response(null, { status: 204 }),
    })
    const user = userEvent.setup()
    const { router } = renderRoutes(routes)

    await user.click(await screen.findByRole('button', { name: 'Terminar sessão' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    const [, init] = fetchMock.mock.calls.find(([url]) => url === '/api/auth/logout')!
    expect(new Headers(init?.headers).get('X-CSRF-Token')).toBe('token-sessao')
  })

  it('aceita apenas destinos internos após o login', () => {
    expect(safeRedirectPath('/issues?id=1')).toBe('/issues?id=1')
    expect(safeRedirectPath('//evil.example')).toBe('/')
    expect(safeRedirectPath('/\\evil.example')).toBe('/')
    expect(safeRedirectPath('https://evil.example')).toBe('/')
    expect(safeRedirectPath(null)).toBe('/')
  })
})
