---
maestru: "0.4"
type: work-spec
id: dev-018-spec
title: "DEV-018 - Fecho e transporte de issues"
template: implementation-plan-v1
work-item: fase-3-scrum/DEV-018
owner: developer
created: 2026-10-20
---

# DEV-018 - Fecho e transporte de issues

## Overview

Fecho de sprints (README §4.4 "Fechar sprint, registar retrospectiva e transportar trabalho incompleto para o backlog ou sprint seguinte", §6 `POST /sprints/{id}/close` e critério MVP "Fechar sprint e preservar compromisso/histórico"). O Tech Lead/Admin fecha o sprint ativo, regista a retrospetiva e escolhe o destino das issues por concluir; o resultado (concluído vs compromisso) fica gravado no sprint e num snapshot de fecho.

### Regras

| Regra | Decisão |
|-------|---------|
| Endpoint | `POST /api/sprints/{id}/close` `{version, carryOverSprintId, retrospective {wentWell, toImprove, actions}}` → sprint `closed` |
| Permissões | `sprints:manage` + acesso (404 sem acesso); projeto arquivado → 422 |
| Estado | Só sprints `active` (422 `field=status`); versão divergente → 409 com `currentVersion` |
| Destino | `carryOverSprintId` `null` = backlog; caso contrário sprint `planned` do mesmo projeto (422 `field=carryOverSprintId`) |
| Retrospetiva | Três textos opcionais, até 5000 caracteres cada |
| Resultado | `result {completedIssueCount, completedStoryPoints, carriedOverIssueCount, carriedOverStoryPoints, carryOverSprintId, committedCompletedIssueCount, committedCompletedStoryPoints}`; "concluída" = estado `done` no fecho |
| Snapshot | `sprint_snapshots` `kind: "closing"` com as issues e o estado no fecho (antes do transporte) |
| Ordem (sem transações) | 1) transição `active → closed` condicional à versão com `result`/`retrospective`; 2) snapshot de fecho (se falhar, o sprint volta a `active`); 3) transporte das issues por concluir, cada uma condicional ao `sprintId` atual e com histórico `sprintId` |
| Transporte | Issues já concluídas ficam no sprint fechado; as restantes vão para o destino. Falhas de transporte individuais (issue movida entretanto) são ignoradas e registadas no log |
| Auditoria | `sprint.closed` com o resumo do resultado |
| Frontend | Página `sprints/:sprintId/close` (destino + retrospetiva + resumo do que será transportado); a página do sprint mostra o resultado e a retrospetiva de um sprint fechado |

## Implementation

### Phase 1 — Backend

- [x] Domínio: `validate_closable`, limites da retrospetiva
- [x] Schemas `SprintClose`, `SprintRetrospective`, `SprintResult` e campos no `SprintResponse`
- [x] `SprintLifecycleService.close` (resultado, snapshot de fecho, transporte, compensação)
- [x] Rota `/close`
- [x] Testes em `tests/test_sprint_lifecycle.py`

### Phase 2 — Frontend

- [x] Serviço/hook `closeSprint`
- [x] Página `SprintClosePage` e rota
- [x] Página do sprint: botão "Fechar sprint", resultado e retrospetiva
- [x] Testes vitest

### Phase 3 — Documentação

- [x] READMEs do backend e do frontend

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/domain/sprints.py` | Modify | Regras de fecho |
| `backend/app/schemas/sprints.py` | Modify | Pedido e resultado do fecho |
| `backend/app/services/sprints.py` | Modify | `result`/`retrospective` na resposta |
| `backend/app/services/sprint_lifecycle.py` | Modify | Fecho e transporte |
| `backend/app/api/routes/sprints.py` | Modify | Rota `/close` |
| `backend/tests/test_sprint_lifecycle.py` | Modify | Testes de fecho |
| `frontend/src/services/sprints.ts` | Modify | API de fecho |
| `frontend/src/features/sprints/useSprints.ts` | Modify | Hook |
| `frontend/src/features/sprints/SprintClosePage.tsx` | Create | Formulário de fecho |
| `frontend/src/features/sprints/SprintDetailPage.tsx` | Modify | Resultado e retrospetiva |
| `frontend/src/app/router.tsx` | Modify | Rota de fecho |
| `frontend/src/features/sprints/sprints.test.tsx` | Modify | Testes |
| `backend/README.md`, `frontend/README.md` | Modify | Documentação |
