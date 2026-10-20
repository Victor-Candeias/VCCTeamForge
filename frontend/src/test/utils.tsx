import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { vi } from 'vitest'
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router'

import { createQueryClient } from '@/app/queryClient'

export function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function renderWithProviders(ui: ReactElement) {
  const queryClient = createQueryClient()
  queryClient.setDefaultOptions({ queries: { retry: false } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

export function renderRoutes(routes: RouteObject[], initialPath = '/') {
  const router = createMemoryRouter(routes, { initialEntries: [initialPath] })
  return { router, ...renderWithProviders(<RouterProvider router={router} />) }
}

type Handler = (init: RequestInit) => Response | Promise<Response>

/**
 * Simula a API: as chaves são "MÉTODO /api/caminho". Pedidos sem handler devolvem 404.
 * Devolve o mock do fetch para verificar chamadas.
 */
export function mockApi(handlers: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const key = `${(init.method ?? 'GET').toUpperCase()} ${String(input)}`
    const handler = handlers[key]
    return handler ? handler(init) : jsonResponse({ title: 'Not Found' }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export const testUser = {
  id: '1',
  email: 'ana@exemplo.pt',
  name: 'Ana',
  role: 'developer' as const,
  permissions: ['issues:read'],
}
