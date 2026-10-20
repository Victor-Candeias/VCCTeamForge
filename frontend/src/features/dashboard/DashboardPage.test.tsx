import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { routes } from '@/app/router'
import { jsonResponse, renderRoutes } from '@/test/utils'

describe('DashboardPage', () => {
  it('mostra o estado da API', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: 'ok', version: '0.1.0' }))
    vi.stubGlobal('fetch', fetchMock)

    renderRoutes(routes)

    expect(await screen.findByText(/Operacional/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/health', expect.anything())
  })

  it('indica quando a API está indisponível', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ title: 'Erro' }, 503)))

    renderRoutes(routes)

    expect(await screen.findByText('API indisponível')).toBeInTheDocument()
  })
})
