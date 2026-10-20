---
maestru: "0.4"
type: work-spec
id: dev-015-spec
title: "DEV-015 - Criar e editar sprints"
template: implementation-plan-v1
work-item: fase-3-scrum/DEV-015
owner: developer
created: 2026-10-20
---

# DEV-015 - Criar e editar sprints

## Overview

Criação, listagem e edição de sprints por projeto (README §4.4 "Criar sprint com nome, objetivo, início e fim", §5.4 e §6 `GET/POST /sprints`). Os sprints nascem no estado `planned`; iniciar (DEV-017) e fechar (DEV-018) ficam fora deste item, mas o modelo já reserva os campos do compromisso (`committedStoryPoints`, `committedIssueCount`, `startedAt`, `closedAt`). A associação de issues e estimativas é o DEV-016.

### Regras

| Regra | Decisão |
|-------|---------|
| Estados | `planned` → `active` → `closed` (só `planned` é criado aqui) |
| Nome | 1–80 caracteres, único por projeto sem distinção de maiúsculas (`nameKey` + índice único) → 409 `field=name` |
| Objetivo | Opcional, ≤ 1000 caracteres |
| Datas | `startDate` obrigatória; `endDate` opcional na criação (omissão = início + `sprintDurationDays` do projeto − 1); `endDate ≥ startDate` e duração ≤ 60 dias → 422 `field=endDate` |
| Sobreposição | As datas não podem sobrepor outro sprint `planned`/`active` do mesmo projeto → 422 `field=startDate` |
| Edição | `planned`: nome, objetivo e datas; `active`: nome, objetivo e `endDate` (início imutável → 422 `field=startDate`); `closed`: só leitura (422) |
| Permissões | Leitura: `projects:read` + acesso ao projeto (404 caso contrário). Escrita: `sprints:manage` (Tech Lead/Admin) + acesso; projeto arquivado → 422 |
| Concorrência | `version` com controlo otimista → 409 com `currentVersion` |
| Auditoria | `sprint.created`, `sprint.updated` (lista de alterações) |
| Listagem | `GET /api/sprints?projectId=&status=&sort=` paginada; `projectId` obrigatório; `sort` `startDate`/`name`/`createdAt` (omissão `-startDate`) |

## Implementation

### Phase 1: Testes

| Action | File | Details |
|--------|------|---------|
| Create | `backend/tests/test_sprints.py` | Criação com/sem `endDate`, validações (nome duplicado, datas, duração, sobreposição), permissões (dev/QA 403, não membro 404), edição por estado, 409 de versão, projeto arquivado, listagem com filtros e auditoria |

### Phase 2: Backend

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/domain/sprints.py` | `SprintStatus`, limites, `can_manage_sprints`, regras de datas |
| Create | `backend/app/repositories/sprints.py` | CRUD com `update_versioned`, `find_overlapping`, nome duplicado |
| Create | `backend/app/schemas/sprints.py` | `SprintCreate`, `SprintUpdate`, `SprintResponse` |
| Create | `backend/app/services/sprints.py` | `SprintService` (search, get, create, update, auditoria) |
| Create | `backend/app/api/routes/sprints.py` | `GET/POST /sprints`, `GET/PATCH /sprints/{id}` |
| Modify | `backend/app/api/router.py` | Registar o router |
| Create | `database/migrations/0004_sprint_collections.py` | Collection `sprints` |
| Modify | `database/indexes/indexes.json` | `sprints_projectId_nameKey_unique`, `sprints_projectId_startDate` |

### Phase 3: Frontend

| Action | File | Details |
|--------|------|---------|
| Create | `frontend/src/services/sprints.ts` | Tipos e cliente da API |
| Create | `frontend/src/features/sprints/useSprints.ts` | Hooks React Query |
| Create | `frontend/src/features/sprints/SprintsPage.tsx` | Tabela de sprints (estado, datas, objetivo) e ações |
| Create | `frontend/src/features/sprints/SprintForm.tsx` | Criar/editar com datas sugeridas pela duração do projeto |
| Modify | `frontend/src/features/projects/projectContext.ts` | Separador Sprints ativo |
| Modify | `frontend/src/app/router.tsx` | `sprints`, `sprints/new`, `sprints/:sprintId/edit` |
| Create | `frontend/src/features/sprints/sprints.test.tsx` | Lista, criação, validação e conflito |

- [x] `pytest`, `ruff`, `npm run typecheck && npm run lint && npm test` passam
- [x] Critério MVP "Criar e iniciar sprint" (parte de criação) verificado na UI (testes de componentes em `sprints.test.tsx`)

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/domain/sprints.py` | Create | Regras |
| `backend/app/repositories/sprints.py` | Create | Persistência |
| `backend/app/schemas/sprints.py` | Create | DTOs |
| `backend/app/services/sprints.py` | Create | Lógica |
| `backend/app/api/routes/sprints.py`, `backend/app/api/router.py` | Create/Modify | API |
| `backend/tests/test_sprints.py` | Create | Testes |
| `database/migrations/0004_sprint_collections.py` | Create | Collection |
| `database/indexes/indexes.json` | Modify | Índices |
| `frontend/src/services/sprints.ts` | Create | Cliente |
| `frontend/src/features/sprints/*` | Create | Páginas, hooks e testes |
| `frontend/src/features/projects/projectContext.ts`, `frontend/src/app/router.tsx` | Modify | Navegação |
| `backend/README.md`, `frontend/README.md` | Modify | Documentação |
