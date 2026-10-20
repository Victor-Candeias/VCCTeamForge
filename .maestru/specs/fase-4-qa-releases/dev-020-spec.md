---
maestru: "0.4"
type: work-spec
id: dev-020-spec
title: "DEV-020 Casos e planos de teste"
template: implementation-plan-v1
work-item: fase-4-qa-releases/DEV-020
owner: developer
created: 2026-10-20
---

# DEV-020 Casos e planos de teste

## Overview

Casos de teste e planos de teste por projeto (README §4.5 "Casos de teste com pré-condições, passos e resultado esperado" e "Planos de teste e associação a projeto, issue e release"; §5.1 `test_cases`/`test_plans`; §6 `GET/POST /test-cases`). As execuções e evidências são o DEV-021; a associação de planos a releases fica para o DEV-022 (a collection `releases` ainda não existe).

### Regras

| Regra | Decisão |
|-------|---------|
| Chave do caso | Número sequencial por projeto (`counters`, `test_cases:<projectId>`); exposto como `TC-<n>` |
| Caso de teste | Título 1–200; descrição e pré-condições ≤ 5000; 1–50 passos `{action (1–1000), expectedResult (≤ 1000)}`; resultado esperado ≤ 2000; prioridade `low`…`critical` (omissão `medium`); labels como nas issues |
| Estados do caso | `draft`, `ready`, `deprecated` (livres entre si); só casos não `deprecated` entram em planos novos/alterados |
| Plano de teste | Nome 1–120, único por projeto sem distinção de maiúsculas (`nameKey`) → 409 `field=name`; descrição ≤ 5000; estados `draft`, `active`, `closed`; plano `closed` só aceita mudar o estado (reabrir) |
| Casos no plano | Até 500 `testCaseIds` do mesmo projeto, sem repetidos (a ordem é mantida) → 422 `field=testCaseIds` |
| Ligação a issues | Até 20 `issueIds` do mesmo projeto, em casos e planos → 422 `field=issueIds` |
| Permissões | Leitura: `tests:read` + acesso ao projeto (404 caso contrário). Escrita: `tests:manage` (QA/Admin) + acesso; projeto arquivado → 422 |
| Concorrência | `version` com controlo otimista → 409 com `currentVersion` |
| Auditoria | `test_case.created/updated`, `test_plan.created/updated` |
| Listagem | Paginada, `projectId` obrigatório. Casos: filtros `status`, `priority`, `label`, `issueId`, `q` (título ou `TC-n`); `sort` `number`/`title`/`priority`/`updatedAt` (omissão `number`). Planos: filtros `status`, `q`; `sort` `name`/`createdAt`/`updatedAt` (omissão `-createdAt`) |

## Implementation

### Phase 1: Backend

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/domain/qa.py` | Estados, limites, normalização de passos e `can_manage_tests` |
| Create | `backend/app/repositories/qa.py` | `TestCaseRepository`, `TestPlanRepository` (duplicado de nome) |
| Create | `backend/app/schemas/qa.py` | Pedidos e respostas de casos e planos |
| Create | `backend/app/services/qa.py` | `TestCaseService`, `TestPlanService` (validação, versões, auditoria) |
| Create | `backend/app/api/routes/qa.py` | `GET/POST /test-cases`, `GET/PATCH /test-cases/{id}`, `GET/POST /test-plans`, `GET/PATCH /test-plans/{id}` |
| Modify | `backend/app/api/router.py` | Incluir as rotas |
| Create | `database/migrations/0005_test_collections.py` | Collections `test_cases`, `test_plans` |
| Modify | `database/indexes/indexes.json` | Únicos `projectId+number` e `projectId+nameKey`; `projectId+status`; `issueIds` |
| Create | `backend/tests/test_qa.py` | Criação, validações, permissões, edição, versões, filtros e auditoria |

### Phase 2: Frontend

| Action | File | Details |
|--------|------|---------|
| Create | `frontend/src/services/testing.ts` | Tipos e cliente da API |
| Create | `frontend/src/features/testing/useTesting.ts` | Hooks React Query |
| Create | `frontend/src/features/testing/TestCasesPage.tsx` | Separador "Testes": casos com filtros e paginação; sub-navegação Casos/Planos |
| Create | `frontend/src/features/testing/TestCaseForm.tsx` | Criar/editar (passos dinâmicos, issues ligadas); só leitura sem `tests:manage` |
| Create | `frontend/src/features/testing/TestPlansPage.tsx` | Lista de planos |
| Create | `frontend/src/features/testing/TestingShared.tsx` | Sub-navegação, badges e seletor de issues ligadas |
| Create | `frontend/src/hooks/useDebouncedValue.ts` | Debounce da pesquisa |
| Create | `frontend/src/features/testing/TestPlanForm.tsx` | Criar/editar com seleção ordenada de casos e issues |
| Modify | `frontend/src/features/projects/projectContext.ts` | Separador Testes ativo |
| Modify | `frontend/src/app/router.tsx` | `tests`, `tests/cases/new`, `tests/cases/:testCaseId`, `tests/plans`, `tests/plans/new`, `tests/plans/:testPlanId` |
| Create | `frontend/src/features/testing/testing.test.tsx` | Lista, criação com passos, só leitura e plano com casos |

- [x] `pytest`, `ruff`, `npm run typecheck && npm run lint && npm test` passam

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/{domain,repositories,schemas,services,api/routes}/…` | Create | API de casos e planos de teste |
| `database/migrations/0005_test_collections.py`, `database/indexes/indexes.json` | Create/Modify | Collections e índices |
| `frontend/src/features/testing/*`, `frontend/src/services/testing.ts` | Create | UI do separador Testes |
| `backend/README.md`, `frontend/README.md` | Modify | Documentação |
