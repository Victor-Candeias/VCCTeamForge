import { useOutletContext } from 'react-router'

import type { Project } from '@/services/projects'

type Tab = { to: string; label: string; end?: boolean; disabled?: boolean }

/** Separadores do projeto; os desativados ficam disponíveis em fases seguintes. */
export const projectTabs: Tab[] = [
  { to: '', label: 'Resumo', end: true },
  { to: 'members', label: 'Membros' },
  { to: 'issues', label: 'Issues' },
  { to: 'backlog', label: 'Backlog', disabled: true },
  { to: 'board', label: 'Quadro', disabled: true },
  { to: 'sprints', label: 'Sprints', disabled: true },
  { to: 'tests', label: 'Testes', disabled: true },
  { to: 'releases', label: 'Releases', disabled: true },
  { to: 'docs', label: 'Documentação', disabled: true },
  { to: 'metrics', label: 'Métricas', disabled: true },
]

export function useProjectContext() {
  return useOutletContext<{ project: Project }>()
}
