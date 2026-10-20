---
maestru: "0.4"
type: work-spec
id: dev-011-spec
title: "DEV-011 - Filtros, paginação e ordenação"
template: implementation-plan-v1
work-item: fase-2-projetos-issues/DEV-011
owner: developer
created: 2026-10-20
---

# DEV-011 - Filtros, paginação e ordenação

## Overview

Pesquisa de issues com filtros por projeto, sprint, estado, prioridade, responsável, tipo e etiqueta (README §4.3), paginação e ordenação com limites (README §6) e projeção apenas dos campos necessários (README §5.6). A UI guarda os filtros no URL para partilha e navegação. Base das vistas de backlog e quadro (DEV-014).

### Contrato `GET /api/issues`

| Parâmetro | Tipo | Regra |
|-----------|------|-------|
| `projectId` | ObjectId, opcional | Sem projeto: pesquisa em todos os projetos acessíveis (`accessible_projects_filter`); projeto inacessível → 404 |
| `status`, `priority`, `type` | lista (repetível) | Valores dos enums; inválido → 422 |
| `assigneeId` | lista | ObjectId, `me` ou `none` |
| `sprintId` | ObjectId ou `none` | `none` = sem sprint (backlog) |
| `label` | lista | Normalizada; corresponde a qualquer (`$in`) |
| `blocked` | bool | |
| `parentIssueId` | ObjectId | Subtarefas/filhos |
| `q` | texto ≤ 100 | `key` exata (ex.: `DVC-12`) ou `title` com regex escapada, sem distinção de maiúsculas |
| `page`, `pageSize` | int | `page ≥ 1`, `1 ≤ pageSize ≤ 100` (default 25) |
| `sort` | `campo` ou `-campo` | `number`, `priority`, `status`, `updatedAt`, `createdAt`, `title`, `dueDate`, `rank` (DEV-014); default `-number`. Desempate por `_id` |

Resposta `Page<IssueSummary>` (`items`, `total`, `page`, `pageSize`) sem `description`, `acceptanceCriteria` nem `dependsOnIssueIds`. Ordenação por prioridade/estado usa `priorityRank`/`statusRank`.

`GET /api/projects/{id}/labels` devolve as etiquetas distintas do projeto (para o filtro).

## Implementation

### Phase 1: Testes

| Action | File | Details |
|--------|------|---------|
| Create | `backend/tests/test_issue_search.py` | Cada filtro isolado e combinado, `me`/`none`, pesquisa por key e título (com caracteres especiais de regex), limites de paginação (422), `total`, ordenação estável, projeção, isolamento entre projetos e utilizadores |

### Phase 2: Backend

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/schemas/issue_search.py` | `IssueSearchQuery` (validação, `sort` → `(campo, direção)`) |
| Modify | `backend/app/repositories/issues.py` | `search(filter, sort, skip, limit, projection)` + `count_documents`; `distinct_labels(project_id)` |
| Modify | `backend/app/services/issues.py` | `build_search_filter(user, query)` com autorização por projeto |
| Modify | `backend/app/api/routes/issues.py` | Parâmetros de lista (`Query(...)` repetíveis) |
| Modify | `backend/app/api/routes/projects.py` | `GET /projects/{id}/labels` |
| Modify | `database/indexes/indexes.json` | `issues_projectId_updatedAt`, `issues_projectId_priorityRank`, `issues_projectId_labels`, `issues_projectId_type` |

- [x] Planos de execução (`explain`) das consultas por projeto usam índice (verificado em teste)

### Phase 3: Frontend

| Action | File | Details |
|--------|------|---------|
| Create | `frontend/src/features/issues/IssueFilters.tsx` | Estado, prioridade, tipo, responsável, etiqueta, bloqueadas, pesquisa (debounce) |
| Create | `frontend/src/features/issues/useIssueSearchParams.ts` | Sincroniza filtros/ordenação/página com `useSearchParams` |
| Create | `frontend/src/components/Pagination.tsx` | Anterior/seguinte, total e tamanho de página |
| Create | `frontend/src/components/SortableHeader.tsx` | Cabeçalho com `aria-sort` |
| Modify | `frontend/src/features/issues/ProjectIssuesPage.tsx` | Usa filtros, paginação e ordenação |
| Modify | `frontend/src/services/issues.ts` | `searchIssues(params)`, `listProjectLabels` |
| Create | `frontend/src/features/issues/issueSearch.test.tsx` | Filtros refletidos no URL e no pedido, paginação, ordenação |

- [x] `pytest`, `ruff`, `npm run typecheck && npm run lint && npm test` passam

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/tests/test_issue_search.py` | Create | Testes |
| `backend/app/schemas/issue_search.py` | Create | Parâmetros de pesquisa |
| `backend/app/repositories/issues.py` | Modify | Pesquisa paginada |
| `backend/app/services/issues.py` | Modify | Filtro autorizado |
| `backend/app/api/routes/issues.py`, `backend/app/api/routes/projects.py` | Modify | API |
| `database/indexes/indexes.json` | Modify | Índices de pesquisa |
| `frontend/src/features/issues/*`, `frontend/src/components/{Pagination,SortableHeader}.tsx` | Create/Modify | UI |
| `frontend/src/services/issues.ts` | Modify | Cliente |
| `backend/README.md` | Modify | Documentação dos parâmetros |
