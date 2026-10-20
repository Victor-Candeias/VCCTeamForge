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

export const techLeadUser = {
  id: 'tl1',
  email: 'tiago@exemplo.pt',
  name: 'Tiago',
  role: 'tech_lead' as const,
  permissions: ['projects:read', 'projects:manage', 'issues:read', 'issues:write', 'issues:comment'],
}

export function testProject(overrides: Record<string, unknown> = {}) {
  return {
    id: 'p1',
    key: 'APP',
    name: 'Aplicação',
    description: 'Projeto de teste',
    status: 'active',
    priority: 'medium',
    lead: { id: 'tl1', name: 'Tiago', email: 'tiago@exemplo.pt', role: 'tech_lead' },
    startDate: '2026-01-05',
    targetDate: null,
    memberCount: 2,
    settings: { methodology: 'scrum', sprintDurationDays: 14, estimationType: 'story_points' },
    createdAt: '2026-01-01T10:00:00Z',
    updatedAt: '2026-01-02T10:00:00Z',
    archivedAt: null,
    version: 3,
    canManage: true,
    ...overrides,
  }
}

export function pageOf<T>(items: T[], page = 1, pageSize = 25) {
  return { items, total: items.length, page, pageSize }
}

/** Handler que simula a obtenção do token CSRF (necessário em POST/PATCH/DELETE). */
export const csrfHandler = {
  'GET /api/auth/csrf': () => {
    document.cookie = 'vcctf_csrf=token-csrf; path=/'
    return jsonResponse({ csrfToken: 'token-csrf' })
  },
}
