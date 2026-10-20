---
maestru: "0.4"
type: work-spec
id: dev-014-spec
title: "DEV-014 - Backlog e quadro Kanban"
template: implementation-plan-v1
work-item: fase-2-projetos-issues/DEV-014
owner: developer
created: 2026-10-20
---

# DEV-014 - Backlog e quadro Kanban

## Overview

Vistas de backlog ordenável e quadro Kanban por estado (README §4.3 "Vistas: tabela, backlog e quadro"). O backlog prioriza issues sem sprint por ordem manual; o quadro permite mover issues entre estados respeitando as transições validadas no backend (DEV-010) e assinala impedimentos. Prepara o quadro Scrum da Fase 3 (o mesmo componente filtrado por sprint).

### Regras

| Regra | Decisão |
|-------|---------|
| Ordem manual | Campo `rank` (float) nas issues; novas issues ficam no fim (`max(rank) + 1024`) |
| Mover no backlog | `POST /api/issues/{id}/rank` com `{beforeId?, afterId?, version}`: novo `rank` = ponto médio entre vizinhos (mesmo projeto); se o intervalo ficar < 1e-6, renormaliza os ranks do projeto (passo 1024) e repete |
| Quem ordena | `issues:write` + regra de edição; Tech Lead/Admin em qualquer issue (prioritização) |
| Backlog | `GET /api/issues?projectId=&sprintId=none&status=…&sort=rank`, sem `done` por omissão; épicos mostrados como agrupador opcional (filtro `type`) |
| Quadro | `GET /api/projects/{id}/board?assigneeId=&type=&label=` → colunas `todo…done` com `IssueSummary` ordenados por `rank`, máx. 200 por coluna (`truncated: true` se exceder); `done` só os últimos 14 dias |
| Mover no quadro | `PATCH /api/issues/{id}` com `status` + `version` (transição validada); opcionalmente `rank` via endpoint de ordem para posição na coluna |
| Conflitos | 409/422 → a UI reverte a atualização otimista, mostra a mensagem e recarrega |
| Acessibilidade | Arrastar e largar (HTML5) com alternativa por teclado/menu ("Mover para…", "Subir", "Descer", "Topo") |

## Implementation

### Phase 1: Testes

| Action | File | Details |
|--------|------|---------|
| Create | `backend/tests/test_board.py` | `rank` inicial, mover entre vizinhos, topo/fim, renormalização, vizinhos de outro projeto → 422, 409 de versão, quadro com colunas, limite e filtro de `done`, transição inválida no quadro → 422 |

### Phase 2: Backend

| Action | File | Details |
|--------|------|---------|
| Modify | `backend/app/services/issues.py` | `rank` na criação, `move_rank`, `board(project, filters)` |
| Modify | `backend/app/repositories/issues.py` | `max_rank`, `renormalize_ranks`, `board_columns` (consulta por coluna com limite) |
| Create | `backend/app/schemas/board.py` | `RankMove`, `BoardColumn`, `Board` |
| Modify | `backend/app/api/routes/issues.py` | `POST /issues/{id}/rank` |
| Modify | `backend/app/api/routes/projects.py` | `GET /projects/{id}/board` |
| Modify | `backend/app/schemas/issue_search.py` | `sort=rank` |
| Create | `database/migrations/0003_issue_rank.py` | Atribui `rank` às issues existentes sem rank (por `number`) |
| Modify | `database/indexes/indexes.json` | `issues_projectId_rank`, `issues_projectId_status_rank` |

### Phase 3: Frontend

| Action | File | Details |
|--------|------|---------|
| Create | `frontend/src/features/issues/BacklogPage.tsx` | Lista ordenada com arrastar/largar e botões subir/descer/topo, filtros básicos, criação rápida |
| Create | `frontend/src/features/issues/BoardPage.tsx` | Colunas por estado, cartões (key, título, tipo, prioridade, responsável, bloqueio), arrastar entre colunas e menu "Mover para", contadores e aviso de truncagem |
| Create | `frontend/src/features/issues/IssueCard.tsx` | Cartão reutilizável |
| Modify | `frontend/src/features/projects/ProjectLayout.tsx` | Separadores Backlog e Quadro ativos |
| Modify | `frontend/src/services/issues.ts` | `moveIssueRank`, `getBoard` |
| Modify | `frontend/src/app/router.tsx` | `/projects/:projectId/backlog`, `/projects/:projectId/board` |
| Create | `frontend/src/features/issues/board.test.tsx` | Mover por menu, reversão em 422, reordenação do backlog |

- [ ] `pytest`, `ruff`, `npm run typecheck && npm run lint && npm test` passam
- [ ] Critérios MVP "Criar, pesquisar e atualizar issues" e "Marcar e consultar impedimentos" verificados na UI

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/tests/test_board.py` | Create | Testes |
| `backend/app/services/issues.py`, `backend/app/repositories/issues.py` | Modify | Ordem e quadro |
| `backend/app/schemas/board.py`, `backend/app/schemas/issue_search.py` | Create/Modify | DTOs |
| `backend/app/api/routes/{issues,projects}.py` | Modify | API |
| `database/migrations/0003_issue_rank.py` | Create | Rank em dados existentes |
| `database/indexes/indexes.json` | Modify | Índices |
| `frontend/src/features/issues/{BacklogPage,BoardPage,IssueCard}.tsx` | Create | Vistas |
| `frontend/src/features/projects/ProjectLayout.tsx`, `frontend/src/app/router.tsx` | Modify | Navegação |
| `frontend/src/services/issues.ts` | Modify | Cliente |
| `backend/README.md`, `frontend/README.md` | Modify | Documentação |
