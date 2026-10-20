---
maestru: "0.4"
type: work-spec
id: dev-010-spec
title: "DEV-010 - CRUD de issues com numeração atómica"
template: implementation-plan-v1
work-item: fase-2-projetos-issues/DEV-010
owner: developer
created: 2026-10-20
---

# DEV-010 - CRUD de issues com numeração atómica

## Overview

Criar, consultar e editar issues de um projeto (README §4.3, §5.3, §5.6 e §6) com identificador sequencial por projeto (`DVC-125`) gerado por `$inc` atómico na collection `counters`. É o núcleo do marco **M2** e a base de DEV-011 (filtros), DEV-012 (comentários/histórico), DEV-013 (anexos) e DEV-014 (backlog/quadro). Depende do DEV-009 (projetos, membros e `key` imutável).

### Regras de domínio

| Regra | Decisão |
|-------|---------|
| Numeração | `CounterRepository.next_value("issues:<projectId>")`; `key = f"{project.key}-{number}"`. Nunca contar documentos. Se o insert falhar depois de reservar o número, fica um intervalo (aceite e documentado) |
| Tipos | `epic`, `story`, `task`, `bug`, `spike`, `improvement`, `subtask` |
| Hierarquia | `subtask` exige `parentIssueId` de um tipo não `epic`/`subtask`; os restantes (exceto `epic`) podem ter como pai apenas um `epic`; `epic` não tem pai. Pai sempre do mesmo projeto. Tipo não editável depois de criado |
| Estados | `todo`, `in_progress`, `code_review`, `testing`, `done`; novas issues começam em `todo` |
| Transições | `ALLOWED_TRANSITIONS` em `app/domain/issues.py`: `todo→in_progress`; `in_progress→todo/code_review/testing/done`; `code_review→in_progress/testing/done`; `testing→in_progress/code_review/done`; `done→in_progress` (reabrir). Inválida → 422. `done` define `completedAt`; reabrir limpa-o |
| Impedimento | `blocked` independente do estado; `blocked=true` exige `blockReason` (1–500); `blocked=false` limpa o motivo; guarda `blockedAt` |
| Prioridade | `low`, `medium`, `high`, `critical` (default `medium`), partilhada com projetos (`app/domain/common.py`, DEV-009) |
| Campos | `title` 1–200; `description` Markdown ≤ 20 000; `storyPoints` 0–100 (múltiplos de 0,5) ou `null`; `labels` ≤ 20, 1–40 caracteres, minúsculas, sem repetidos; `acceptanceCriteria` ≤ 50 itens ≤ 500; `dependsOnIssueIds` ≤ 50, mesmo projeto, sem a própria; `dueDate` opcional |
| Ordenação | Campos derivados `priorityRank` (critical=4…low=1) e `statusRank` (todo=1…done=5) gravados em cada escrita (usados no DEV-011) |
| Sprint | `sprintId` existe no documento (`null`) mas só é editável na Fase 3 |
| Responsável | `assigneeId` tem de ser utilizador ativo e membro (ou lead) do projeto; `reporterId` = utilizador autenticado |
| Permissões | Ler: `issues:read` + acesso ao projeto (404 caso contrário). Criar: `issues:write` + acesso; QA só cria `bug`. Editar: Admin/Tech Lead em qualquer issue do projeto; Developer/QA só em issues atribuídas a si ou que reportaram (403) |
| Projeto arquivado | Criar/editar issues → 422 |
| Concorrência | `version` obrigatório no PATCH; filtro `{_id, version}` + `$inc` → 409 se divergir |
| Remoção | Sem DELETE (preserva histórico); fora de âmbito nesta fase |

### Contratos API

| Método | Endpoint | Permissão | Resposta |
|--------|----------|-----------|----------|
| GET | `/api/issues?projectId=&page=&pageSize=` | `issues:read` | `Page<IssueSummary>` ordenada por `number` desc (filtros completos no DEV-011) |
| POST | `/api/issues` | `issues:write` | 201 + `Issue` |
| GET | `/api/issues/{id}` | `issues:read` + acesso | `Issue` com `assignee`, `reporter`, `parent` resumidos |
| GET | `/api/issues/by-key/{key}` | `issues:read` + acesso | `Issue` (para URLs legíveis) |
| PATCH | `/api/issues/{id}` | `issues:write` + regra de edição | `Issue` (body com `version`) |

## Implementation

### Phase 1: Testes e domínio

| Action | File | Details |
|--------|------|---------|
| Create | `backend/tests/test_issues.py` | Integração: numeração sequencial por projeto e independente entre projetos (inclui criação concorrente com threads → números únicos), `key`, validações de campos, hierarquia, responsável não membro → 422, transições válidas/inválidas, `completedAt`, bloqueio, regras de edição por perfil, QA só bugs, projeto arquivado, 409 de versão, acesso a projeto alheio → 404, CSRF |
| Create | `backend/tests/test_issue_domain.py` | Unitários: transições, normalização de labels, ranks, validação de hierarquia |
| Create | `backend/app/domain/issues.py` | `IssueType`, `IssueStatus`, `ALLOWED_TRANSITIONS`, `STATUS_RANK`, `validate_transition`, `normalize_labels`, `validate_parent`, `can_edit_issue(user, issue)` |
| Create | `backend/app/schemas/issues.py` | `IssueCreate`, `IssueUpdate` (`extra="forbid"`, `version`), `Issue`, `IssueSummary`, `UserRef`, `IssueRef` |

### Phase 2: Persistência, serviço e API

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/repositories/issues.py` | `create`, `find_by_id`, `find_by_key`, `find_many_by_ids`, `list_page`, `update_versioned` |
| Create | `backend/app/services/issues.py` | `IssueService`: reserva de número, validações, ranks, regras de edição, carregamento de referências (utilizadores/pai) em lote |
| Create | `backend/app/api/routes/issues.py` | Endpoints acima |
| Modify | `backend/app/api/router.py` | Incluir `issues.router` |
| Create | `database/migrations/0002_issue_collections.py` | Cria `issues`, `issue_comments`, `issue_history`, `attachments` (idempotente) |
| Modify | `database/indexes/indexes.json` | `issues_key_unique`, `issues_parentIssueId` |

- [ ] `VCCTF_REQUIRE_MONGO=1 .venv/bin/pytest` e `ruff` passam

### Phase 3: Frontend

| Action | File | Details |
|--------|------|---------|
| Create | `frontend/src/services/issues.ts` | Tipos, rótulos PT (tipo, estado, prioridade) e chamadas |
| Create | `frontend/src/features/issues/useIssues.ts` | Hooks TanStack Query |
| Create | `frontend/src/features/issues/ProjectIssuesPage.tsx` | Separador "Issues" do projeto: tabela paginada + "Nova issue" |
| Create | `frontend/src/features/issues/IssueForm.tsx` | Criar/editar (react-hook-form + zod): tipo, título, descrição, prioridade, responsável (membros do projeto), story points, labels, critérios de aceitação, pai, data limite |
| Create | `frontend/src/features/issues/IssueDetailPage.tsx` | Detalhe com mudança de estado (só transições válidas), bloquear/desbloquear com motivo, descrição Markdown sanitizada |
| Create | `frontend/src/components/Markdown.tsx` | `react-markdown` sem HTML bruto (`skipHtml`) e links com `rel="noopener noreferrer"` |
| Modify | `frontend/package.json` | `react-markdown` |
| Modify | `frontend/src/app/router.tsx` | `/projects/:projectId/issues`, `/projects/:projectId/issues/new`, `/issues/:issueKey`, `/issues/:issueKey/edit` |
| Create | `frontend/src/features/issues/issues.test.tsx` | Criação, validação, transições disponíveis, bloqueio, 409 |

- [ ] `npm run typecheck && npm run lint && npm test` passam

### Phase 4: Documentação

| Action | File | Details |
|--------|------|---------|
| Modify | `backend/README.md` | Endpoints de issues, regras de transição e numeração |
| Run | `maestru check` | DEV-010 → `done` |

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/tests/test_issues.py`, `backend/tests/test_issue_domain.py` | Create | Testes |
| `backend/app/domain/issues.py` | Create | Regras de domínio das issues |
| `backend/app/schemas/issues.py` | Create | DTOs |
| `backend/app/repositories/issues.py` | Create | Persistência |
| `backend/app/services/issues.py` | Create | Regras de negócio |
| `backend/app/api/routes/issues.py`, `backend/app/api/router.py` | Create/Modify | API |
| `database/migrations/0002_issue_collections.py` | Create | Collections da Fase 2 |
| `database/indexes/indexes.json` | Modify | Índices |
| `frontend/src/services/issues.ts`, `frontend/src/features/issues/*` | Create | UI de issues |
| `frontend/src/components/Markdown.tsx`, `frontend/package.json` | Create/Modify | Markdown seguro |
| `frontend/src/app/router.tsx` | Modify | Rotas |
| `backend/README.md` | Modify | Documentação |
