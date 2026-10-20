---
maestru: "0.4"
type: work-spec
id: dev-021-spec
title: "DEV-021 Execuções e evidências"
template: implementation-plan-v1
work-item: fase-4-qa-releases/DEV-021
owner: developer
created: 2026-10-20
---

# DEV-021 Execuções e evidências

## Overview

Registo de execuções de casos de teste, evidências em anexo, criação de bug a partir de uma execução falhada e progresso/regressão por plano (README §4.5 "Execuções com estados `pass`, `fail`, `blocked`, `not_run`, `skipped`", "Evidências em anexo, executor, data e observações", "Criar bug a partir de uma execução falhada mantendo a ligação", "Relatórios de execução e regressão"; §5.1 `test_runs`; §6 `POST /test-runs`). A associação de execuções a releases fica para o DEV-022.

### Regras

| Regra | Decisão |
|-------|---------|
| Execução | Caso de teste obrigatório (não `deprecated`); plano opcional (não `closed`) que contenha o caso → 422 `field=testPlanId`/`testCaseId` |
| Resultado | `pass`, `fail`, `blocked`, `not_run`, `skipped` |
| Campos | `actualResult` ≤ 5000, `notes` ≤ 5000, `environment` ≤ 200; `executedAt` opcional (omissão: agora; nunca no futuro → 422) |
| Snapshot | Guarda `testCaseNumber` e `testCaseTitle` no momento da execução (histórico estável) |
| Permissões | Leitura: `tests:read` + acesso ao projeto (404 caso contrário). Registar: `tests:execute` (QA/Admin) + acesso; projeto arquivado → 422. Editar: `tests:execute` e ser o executor, ou `tests:manage` |
| Concorrência | `version` com controlo otimista → 409 com `currentVersion` |
| Evidências | Collection `attachments` com `testRunId` (sem `issueId`); mesma validação de tipo/assinatura/tamanho dos anexos; máximo `ATTACHMENTS_MAX_PER_ISSUE` por execução; remoção por quem carregou, executor com `tests:manage`, responsável do projeto ou admin (soft delete) |
| Bug a partir da execução | `POST /test-runs/{id}/bugs` só para resultado `fail`; cria issue `bug` (permissões e regras das issues) com descrição pré-preenchida (caso, passos, esperado vs. obtido) e guarda o id em `bugIssueIds` (máx. 20) |
| Pass rate | `pass / (pass + fail + blocked)` como fração 0–1; `skipped` e `not_run` não contam; `null` sem execuções relevantes |
| Progresso do plano | `GET /test-plans/{id}/progress`: último resultado por caso, resultado anterior, `regression` quando o anterior foi `pass` e o último `fail`; totais por resultado (casos sem execução contam como `not_run`) |
| Auditoria | `test_run.created/updated/bug_created`, `test_run_evidence.created/deleted` |
| Listagem | Paginada, `projectId` obrigatório; filtros `testCaseId`, `testPlanId`, `result`, `executedBy` (`me`); `sort` `executedAt` (omissão `-executedAt`) |

## Implementation

### Phase 1: Backend

| Action | File | Details |
|--------|------|---------|
| Modify | `backend/app/domain/qa.py` | `TestRunResult`, limites e `pass_rate` |
| Modify | `backend/app/repositories/qa.py` | `TestRunRepository` (pesquisa, últimas execuções por caso no plano) |
| Modify | `backend/app/repositories/attachments.py` | Consultas de evidências; anexos de issues só com `issueId` |
| Modify | `backend/app/services/attachments.py` | `store_upload` partilhado (validação e gravação) |
| Create | `backend/app/services/test_runs.py` | `TestRunService` (registo, edição, bug, progresso) e `TestRunEvidenceService` |
| Modify | `backend/app/schemas/qa.py` | Pedidos e respostas de execuções, evidências e progresso |
| Modify | `backend/app/api/routes/qa.py` | `GET/POST /test-runs`, `GET/PATCH /test-runs/{id}`, `POST /test-runs/{id}/bugs`, evidências e `GET /test-plans/{id}/progress` |
| Create | `database/migrations/0007_test_runs.py` | Collection `test_runs` |
| Modify | `database/indexes/indexes.json` | `test_runs` por caso/plano e `attachments` por `testRunId` |
| Create | `backend/tests/test_test_runs.py` | Registo, validações, permissões, edição, evidências, bug e progresso |

### Phase 2: Frontend

| Action | File | Details |
|--------|------|---------|
| Modify | `frontend/src/services/testing.ts` | Tipos e cliente da API de execuções/evidências/progresso |
| Modify | `frontend/src/features/testing/useTesting.ts` | Hooks React Query |
| Modify | `frontend/src/features/testing/TestingShared.tsx` | Sub-navegação "Execuções" e `TestRunResultBadge` |
| Create | `frontend/src/features/testing/TestRunsPage.tsx` | Lista com filtros de resultado e plano |
| Create | `frontend/src/features/testing/TestRunForm.tsx` | Registar execução (caso, plano, resultado, observações) |
| Create | `frontend/src/features/testing/TestRunDetailPage.tsx` | Detalhe, edição do resultado, evidências e criação de bug |
| Create | `frontend/src/features/testing/TestPlanProgress.tsx` | Progresso e regressões no plano, com atalho "Executar" |
| Modify | `frontend/src/features/testing/TestPlanForm.tsx` | Mostrar o progresso no plano |
| Modify | `frontend/src/features/testing/TestCaseForm.tsx` | Botões "Executar" e "Ver execuções" no caso |
| Modify | `frontend/src/app/router.tsx` | `tests/runs`, `tests/runs/new`, `tests/runs/:testRunId` |
| Create | `frontend/src/features/testing/testRuns.test.tsx` | Lista, registo, bug a partir de falha e progresso |

- [x] `pytest`, `ruff`, `npm run typecheck && npm run lint && npm test` passam

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/{domain,repositories,schemas,services,api/routes}/…` | Create/Modify | API de execuções e evidências |
| `database/migrations/0007_test_runs.py`, `database/indexes/indexes.json` | Create/Modify | Collection e índices |
| `frontend/src/features/testing/*`, `frontend/src/services/testing.ts` | Create/Modify | UI de execuções |
| `backend/README.md`, `frontend/README.md` | Modify | Documentação |
