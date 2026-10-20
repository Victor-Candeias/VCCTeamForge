---
maestru: "0.4"
type: work-spec
id: dev-016-spec
title: "DEV-016 - Planeamento e estimativas"
template: implementation-plan-v1
work-item: fase-3-scrum/DEV-016
owner: developer
created: 2026-10-20
---

# DEV-016 - Planeamento e estimativas

## Overview

Planeamento de sprints (README §4.4 "Associar issues do backlog e definir estimativas" e critério MVP "Adicionar e estimar issues numa sprint"). O Tech Lead/Admin associa issues do backlog a um sprint `planned`/`active`, retira-as de volta para o backlog e estima-as (story points) na própria página do sprint; cada sprint passa a ter uma capacidade opcional e totais de âmbito calculados. Iniciar (compromisso) e fechar ficam para DEV-017/DEV-018.

### Regras

| Regra | Decisão |
|-------|---------|
| Endpoints | `POST /api/sprints/{id}/issues` `{issueIds}` (1–50) e `DELETE /api/sprints/{id}/issues/{issueId}`; ambos devolvem o sprint com os totais atualizados |
| Permissões | `sprints:manage` + acesso ao projeto (404 sem acesso); projeto arquivado ou sprint `closed` → 422 |
| Issues elegíveis | Mesmo projeto, não `done` e não `epic` → 422 `field=issueIds` (com `issueKey`) |
| Origem | Issue no backlog ou noutro sprint `planned`/`active` (é movida); issue num sprint fechado → 422; já no sprint → ignorada (idempotente) |
| Limite | No máximo 300 issues por sprint → 422 |
| Concorrência | Atualização condicional ao `sprintId` lido (`find_one_and_update`), incrementa `version` da issue; divergência → 409 com `issueKey` |
| Histórico | Cada issue regista `updated` com a alteração `sprintId` (de/para, com o nome do sprint); auditoria `sprint.issues_added` / `sprint.issue_removed` no sprint |
| Estimativas | Story points editados com `PATCH /api/issues/{id}` (validação existente: 0–100, múltiplos de 0,5, `version`) |
| Capacidade | `capacityStoryPoints` opcional (0–1000, múltiplos de 0,5) na criação/edição do sprint |
| Totais | `scope` no `SprintResponse`: `issueCount`, `storyPoints`, `unestimatedCount`, `completedIssueCount`, `completedStoryPoints` (agregação por `sprintId` sobre o índice `issues_sprintId_status`) |

## Implementation

### Phase 1: Testes

| Action | File | Details |
|--------|------|---------|
| Create | `backend/tests/test_sprint_planning.py` | Adicionar/mover/remover, totais, elegibilidade (epic, done, outro projeto, sprint fechado), limite, permissões, arquivado, histórico/auditoria, capacidade |
| Modify | `frontend/src/features/sprints/sprints.test.tsx` | Página do sprint: totais, adicionar do backlog, remover, estimar |

### Phase 2: Backend

| Action | File | Details |
|--------|------|---------|
| Modify | `backend/app/domain/sprints.py` | `SPRINT_ISSUES_MAX`, `CAPACITY_MAX`, `validate_plannable`, `validate_capacity` |
| Modify | `backend/app/repositories/issues.py` | `sprint_totals`, `set_sprint` (condicional), `count_in_sprint` |
| Modify | `backend/app/schemas/sprints.py` | `capacityStoryPoints`, `SprintScope`, `SprintIssuesAdd` |
| Modify | `backend/app/services/sprints.py` | Capacidade e `scope` nas respostas |
| Create | `backend/app/services/sprint_planning.py` | `SprintPlanningService.add_issues/remove_issue` |
| Modify | `backend/app/api/routes/sprints.py` | Novos endpoints |

### Phase 3: Frontend

| Action | File | Details |
|--------|------|---------|
| Modify | `frontend/src/services/sprints.ts` | Tipos `scope`/capacidade, `addSprintIssues`, `removeSprintIssue` |
| Modify | `frontend/src/features/sprints/useSprints.ts` | Mutações que invalidam sprints, issues e quadro |
| Create | `frontend/src/features/sprints/SprintDetailPage.tsx` | Cabeçalho, totais vs capacidade, issues do sprint (estimativa inline e remover) e backlog elegível (adicionar) |
| Create | `frontend/src/features/sprints/EstimateInput.tsx` | Edição inline de story points |
| Modify | `frontend/src/features/sprints/SprintForm.tsx` | Campo capacidade |
| Modify | `frontend/src/features/sprints/SprintsPage.tsx` | Nome liga ao detalhe; colunas Issues e SP |
| Modify | `frontend/src/app/router.tsx` | `sprints/:sprintId` |

- [x] `pytest`, `ruff`, `npm run typecheck && npm run lint && npm test` passam
- [x] Critério MVP "Adicionar e estimar issues numa sprint" coberto por testes de API e de componentes

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/domain/sprints.py` | Modify | Regras |
| `backend/app/repositories/issues.py` | Modify | Totais e associação |
| `backend/app/schemas/sprints.py` | Modify | DTOs |
| `backend/app/services/sprints.py`, `backend/app/services/sprint_planning.py` | Modify/Create | Lógica |
| `backend/app/api/routes/sprints.py` | Modify | API |
| `backend/tests/test_sprint_planning.py` | Create | Testes |
| `frontend/src/services/sprints.ts`, `frontend/src/features/sprints/*` | Modify/Create | Cliente, páginas, hooks e testes |
| `frontend/src/app/router.tsx` | Modify | Navegação |
| `backend/README.md`, `frontend/README.md` | Modify | Documentação |
