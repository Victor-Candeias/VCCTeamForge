---
maestru: "0.4"
type: work-spec
id: dev-022-spec
title: "DEV-022 Releases e checklists"
template: implementation-plan-v1
work-item: fase-4-qa-releases/DEV-022
owner: developer
created: 2026-10-20
---

# DEV-022 Releases e checklists

## Overview

Gestão de releases por projeto (README §4.6 "Versão, descrição, datas, issues incluídas, bugs conhecidos e notas", "Workflow `draft` → `ready_for_qa` → `approved` → `released`", "Checklist e critérios configuráveis para aprovação", "Histórico de aprovações e alterações"; §4.5 "Planos de teste e associação a … release"; §5.1 `releases`; §6 `GET/POST /releases`; §9 "Release Quality"). Ativa o separador "Releases" do projeto.

### Regras

| Regra | Decisão |
|-------|---------|
| Identificação | `name` = número da versão (ex.: `1.4.0`), 1–40 caracteres `[0-9A-Za-z._+-]`, único por projeto sem distinção de maiúsculas → 409 `field=name` (o campo `version` é o controlo otimista) |
| Conteúdo | `description` ≤ 5000, `notes` (notas de release, markdown) ≤ 20000, `plannedDate` opcional, `releasedAt` definido ao publicar |
| Ligações | `issueIds` ≤ 500, `knownBugIds` ≤ 100 (só issues `bug`), `testPlanIds` ≤ 50; todas do mesmo projeto → 422 com `field` |
| Checklist | ≤ 30 itens `{id, label ≤ 200, required, done, doneBy, doneAt}`; ao criar sem checklist copia os itens (por marcar) da release mais recente do projeto ou usa a checklist por omissão |
| Critérios | `criteria = {issuesDone, testsPassed, noOpenCriticalBugs}` (todos `true` por omissão), avaliados em cada leitura e obrigatórios na aprovação |
| Avaliação | `issuesDone`: todas as issues incluídas `done`. `testsPassed`: pelo menos um plano associado e último resultado de todos os casos `pass` ou `skipped`. `noOpenCriticalBugs`: nenhum bug conhecido ou incluído com prioridade `critical` por concluir |
| Workflow | `draft→ready_for_qa` (`releases:manage`); `ready_for_qa→approved` (`releases:approve`, checklist obrigatória marcada e critérios ativos cumpridos → 422 `field=checklist`/`criteria`); `ready_for_qa→draft` e `approved→draft` (`releases:manage` ou `releases:approve`, comentário obrigatório); `approved→released` (`releases:manage`). `released` é final |
| Edição | `PATCH` com `releases:manage` só em `draft`/`ready_for_qa`; `approved`/`released` ficam só de leitura |
| Histórico | `history` na release (máx. 500 entradas): `created`, `updated` (campos alterados), `submitted`, `approved`, `rejected`, `reopened`, `released`, com utilizador, data e comentário; auditoria `release.created/updated/transitioned` |
| Permissões | Leitura `releases:read` + acesso ao projeto (404 caso contrário); projeto arquivado → só leitura (422) |
| Qualidade | Resposta inclui issues concluídas, bugs conhecidos abertos/críticos e agregado dos planos associados (contagens, pass rate, regressões) |

## Implementation

### Phase 1: Backend

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/domain/releases.py` | Estados, transições, limites, checklist por omissão e permissões |
| Create | `backend/app/repositories/releases.py` | `ReleaseRepository` (pesquisa, unicidade do nome, versão otimista, histórico com `$slice`) |
| Create | `backend/app/schemas/releases.py` | Pedidos e respostas (lista, detalhe, qualidade, histórico) |
| Create | `backend/app/services/releases.py` | `ReleaseService` (CRUD, checklist, critérios, workflow, qualidade) |
| Modify | `backend/app/services/test_runs.py` | Agregado de progresso reutilizável por vários planos |
| Create | `backend/app/api/routes/releases.py` | `GET/POST /releases`, `GET/PATCH /releases/{id}`, `POST /releases/{id}/transitions` |
| Modify | `backend/app/api/router.py` | Registar o router |
| Create | `database/migrations/0008_releases.py` | Collection `releases` |
| Modify | `database/indexes/indexes.json` | `releases_projectId_nameKey_unique`, `releases_projectId_createdAt` |
| Create | `backend/tests/test_releases.py` | CRUD, validações, checklist, critérios, workflow, permissões e histórico |

### Phase 2: Frontend

| Action | File | Details |
|--------|------|---------|
| Create | `frontend/src/services/releases.ts` | Tipos e cliente da API |
| Create | `frontend/src/features/releases/useReleases.ts` | Hooks React Query |
| Create | `frontend/src/features/releases/ReleasesPage.tsx` | Lista com filtro de estado |
| Create | `frontend/src/features/releases/ReleaseForm.tsx` | Criar/editar (ligações, checklist e critérios) |
| Create | `frontend/src/features/releases/ReleaseDetailPage.tsx` | Qualidade, critérios, checklist, transições e histórico |
| Modify | `frontend/src/features/testing/TestingShared.tsx` | `IssueLinks` configurável (rótulo e tipos) |
| Modify | `frontend/src/features/projects/projectContext.ts` | Ativar o separador "Releases" |
| Modify | `frontend/src/app/router.tsx` | `releases`, `releases/new`, `releases/:releaseId`, `releases/:releaseId/edit` |
| Create | `frontend/src/features/releases/releases.test.tsx` | Lista, criação, aprovação bloqueada e transições |

- [x] `pytest`, `ruff`, `npm run typecheck && npm run lint && npm test` passam

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/{domain,repositories,schemas,services,api}/…` | Create/Modify | API de releases |
| `database/migrations/0008_releases.py`, `database/indexes/indexes.json` | Create/Modify | Collection e índices |
| `frontend/src/features/releases/*`, `frontend/src/services/releases.ts` | Create | UI de releases |
| `backend/README.md`, `frontend/README.md` | Modify | Documentação |
