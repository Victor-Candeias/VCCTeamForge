import { createBrowserRouter, type RouteObject } from 'react-router'

import { AppLayout } from '@/app/layout/AppLayout'
import { NotFoundPage } from '@/app/NotFoundPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { ProjectCreatePage, ProjectEditPage } from '@/features/projects/ProjectForm'
import { ProjectLayout } from '@/features/projects/ProjectLayout'
import { ProjectMembers } from '@/features/projects/ProjectMembers'
import { ProjectsPage } from '@/features/projects/ProjectsPage'
import { ProjectSummaryPage } from '@/features/projects/ProjectSummaryPage'

export const routes: RouteObject[] = [
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        path: '/',
        element: <AppLayout />,
        children: [
          { index: true, element: <DashboardPage /> },
          { path: 'projects', element: <ProjectsPage /> },
          { path: 'projects/new', element: <ProjectCreatePage /> },
          { path: 'projects/:projectId/edit', element: <ProjectEditPage /> },
          {
            path: 'projects/:projectId',
            element: <ProjectLayout />,
            children: [
              { index: true, element: <ProjectSummaryPage /> },
              { path: 'members', element: <ProjectMembers /> },
            ],
          },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]

export function createAppRouter() {
  return createBrowserRouter(routes)
}
