import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { routes } from '@/app/router'
import { jsonResponse, mockApi, renderRoutes, testUser } from '@/test/utils'

describe('DashboardPage', () => {
  it('mostra o estado da API', async () => {
    const fetchMock = mockApi({
      'GET /api/users/me': () => jsonResponse(testUser),
      'GET /api/health': () => jsonResponse({ status: 'ok', version: '0.1.0' }),
    })

    renderRoutes(routes)

    expect(await screen.findByText(/Operacional/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/health', expect.anything())
  })

  it('indica quando a API está indisponível', async () => {
    mockApi({
      'GET /api/users/me': () => jsonResponse(testUser),
      'GET /api/health': () => jsonResponse({ title: 'Erro' }, 503),
    })

    renderRoutes(routes)

    expect(await screen.findByText('API indisponível')).toBeInTheDocument()
  })
})
