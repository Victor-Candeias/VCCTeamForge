---
maestru: "0.4"
type: work-spec
id: dev-017-spec
title: "DEV-017 - Início e snapshot do compromisso"
template: implementation-plan-v1
work-item: fase-3-scrum/DEV-017
owner: developer
created: 2026-10-20
---

# DEV-017 - Início e snapshot do compromisso

## Overview

Início de sprints (README §4.4 "Iniciar sprint", §5.6 "Ao iniciar uma sprint, guardar snapshot do compromisso" e §6 `POST /sprints/{id}/start`). O Tech Lead/Admin inicia um sprint planeado; o sistema congela o compromisso (issues e story points) num snapshot imutável, que serve de base às métricas de previsibilidade e ao burndown (DEV-019). O quadro passa a poder ser filtrado por sprint.

### Regras

| Regra | Decisão |
|-------|---------|
| Endpoint | `POST /api/sprints/{id}/start` `{version}` → sprint `active` |
| Permissões | `sprints:manage` + acesso (404 sem acesso); projeto arquivado → 422 |
| Estado | Só sprints `planned` (422 `field=status`); versão divergente → 409 com `currentVersion` |
| Um ativo por projeto | Pré-verificação (422 `field=status`, com `sprintId` do ativo) + índice único parcial `sprints_projectId_active_unique` (`{projectId}` com `status: "active"`) para pedidos concorrentes |
| Datas | `endDate` anterior a hoje (UTC) → 422 `field=endDate`; as datas planeadas mantêm-se |
| Âmbito | Sprint sem issues → 422 `field=issueIds` |
| Compromisso | `committedIssueCount`/`committedStoryPoints` (issues sem estimativa contam 0), `startedAt`, `startedBy` gravados na transição |
| Snapshot | `sprint_snapshots` `{sprintId, projectId, kind: "commitment", day, takenAt, issues[{issueId, key, title, type, status, storyPoints, assigneeId}], totals}`; índice único `(sprintId, kind, day)` |
| Consistência | Sem transações: primeiro a transição do sprint (condicional a `version` e `status=planned`), depois o snapshot; se o snapshot falhar, o sprint volta a `planned` (compensação) e o pedido falha |
| Consulta | `GET /api/sprints/{id}/commitment` (`projects:read`): totais, issues comprometidas (estado atual e se ainda estão no sprint) e issues adicionadas depois do início; 404 se o sprint não foi iniciado |
| Auditoria | `sprint.started` com os totais do compromisso |
| Frontend | Botão "Iniciar sprint" com confirmação na página do sprint; secção "Compromisso"; filtro de sprint no quadro (`?sprintId=`) |

## Implementation

### Phase 1 — Backend

- [x] Domínio: `validate_startable` (estado, data de fim, âmbito)
- [x] Repositório `SprintSnapshotRepository` (upsert por `sprintId`/`kind`/`day`, leitura)
- [x] `SprintRepository.transition` (condicional a versão e estado; `DuplicateKeyError` do índice de ativo → erro próprio)
- [x] `SprintLifecycleService.start` e `commitment`; rotas `/start` e `/commitment`
- [x] Índices (`sprints_projectId_active_unique`, `sprint_snapshots_sprintId_kind_day_unique`) e migration `0006_sprint_snapshots`
- [x] Testes `tests/test_sprint_lifecycle.py`

### Phase 2 — Frontend

- [x] Serviços/hooks `startSprint` e `getSprintCommitment`
- [x] Página do sprint: iniciar com confirmação e secção de compromisso
- [x] Quadro: seletor de sprint ligado a `?sprintId=`
- [x] Testes vitest

### Phase 3 — Documentação

- [x] READMEs do backend e do frontend

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/domain/sprints.py` | Modify | Regras de início |
| `backend/app/repositories/sprints.py` | Modify | Transição condicional e erro de sprint ativo |
| `backend/app/repositories/sprint_snapshots.py` | Create | Snapshots de sprint |
| `backend/app/services/sprint_lifecycle.py` | Create | Início e compromisso |
| `backend/app/schemas/sprints.py` | Modify | `SprintStart`, `SprintCommitment` |
| `backend/app/api/routes/sprints.py` | Modify | Rotas `/start` e `/commitment` |
| `database/indexes/indexes.json` | Modify | Índices novos |
| `database/migrations/0006_sprint_snapshots.py` | Create | Collection `sprint_snapshots` |
| `backend/tests/test_sprint_lifecycle.py` | Create | Testes de início |
| `frontend/src/services/sprints.ts` | Modify | API de início e compromisso |
| `frontend/src/features/sprints/useSprints.ts` | Modify | Hooks |
| `frontend/src/features/sprints/SprintDetailPage.tsx` | Modify | Iniciar e compromisso |
| `frontend/src/features/sprints/SprintCommitment.tsx` | Create | Secção de compromisso |
| `frontend/src/features/issues/BoardPage.tsx` | Modify | Filtro de sprint |
| `frontend/src/features/sprints/sprints.test.tsx` | Modify | Testes |
| `backend/README.md`, `frontend/README.md` | Modify | Documentação |
