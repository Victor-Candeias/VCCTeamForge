import { createBrowserRouter, type RouteObject } from 'react-router'

import { AppLayout } from '@/app/layout/AppLayout'
import { NotFoundPage } from '@/app/NotFoundPage'
import { AuditLogPage } from '@/features/admin/AuditLogPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { IssueDetailPage } from '@/features/issues/IssueDetailPage'
import { IssueCreatePage, IssueEditPage } from '@/features/issues/IssueForm'
import { BacklogPage } from '@/features/issues/BacklogPage'
import { BoardPage } from '@/features/issues/BoardPage'
import { ProjectIssuesPage } from '@/features/issues/ProjectIssuesPage'
import { ProjectCreatePage, ProjectEditPage } from '@/features/projects/ProjectForm'
import { ProjectLayout } from '@/features/projects/ProjectLayout'
import { ProjectMembers } from '@/features/projects/ProjectMembers'
import { ProjectsPage } from '@/features/projects/ProjectsPage'
import { ProjectSummaryPage } from '@/features/projects/ProjectSummaryPage'
import { SprintCreatePage, SprintEditPage } from '@/features/sprints/SprintForm'
import { SprintsPage } from '@/features/sprints/SprintsPage'

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
              { path: 'issues', element: <ProjectIssuesPage /> },
              { path: 'backlog', element: <BacklogPage /> },
              { path: 'board', element: <BoardPage /> },
              { path: 'issues/new', element: <IssueCreatePage /> },
              { path: 'sprints', element: <SprintsPage /> },
              { path: 'sprints/new', element: <SprintCreatePage /> },
              { path: 'sprints/:sprintId/edit', element: <SprintEditPage /> },
            ],
          },
          { path: 'issues/:issueKey', element: <IssueDetailPage /> },
          { path: 'issues/:issueKey/edit', element: <IssueEditPage /> },
          { path: 'admin/audit', element: <AuditLogPage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]

export function createAppRouter() {
  return createBrowserRouter(routes)
}
