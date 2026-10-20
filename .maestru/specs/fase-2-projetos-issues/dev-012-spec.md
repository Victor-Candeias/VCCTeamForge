---
maestru: "0.4"
type: work-spec
id: dev-012-spec
title: "DEV-012 - Comentários, histórico e auditoria"
template: implementation-plan-v1
work-item: fase-2-projetos-issues/DEV-012
owner: developer
created: 2026-10-20
---

# DEV-012 - Comentários, histórico e auditoria

## Overview

Comentários em issues, histórico consultável de alterações e auditoria das mutações (README §4.3, §5.1, §5.6, §6 e §4.8). Comentários e histórico ficam em collections separadas (`issue_comments`, `issue_history`) para evitar arrays ilimitados. Inclui a consulta dos logs de auditoria para quem tem `audit:read`. Critério MVP: "Comentários e histórico consultável".

### Regras

| Regra | Decisão |
|-------|---------|
| Comentar | `issues:comment` + acesso ao projeto; projeto arquivado → 422; `body` Markdown 1–10 000 |
| Editar comentário | Só o autor; guarda `editedAt` |
| Apagar comentário | Autor, lead do projeto ou admin; *soft delete* (`deletedAt`, `deletedBy`, `body` removido); aparece como "Comentário removido" |
| Histórico | Evento por mutação: `created`, `updated` (lista `changes: [{field, from, to}]` só com campos alterados; descrição/critérios registam apenas que mudaram), `comment_added`, `comment_edited`, `comment_deleted`; DEV-013 acrescenta `attachment_added`/`attachment_removed` |
| Consistência | Sem transações: o histórico é escrito logo após a mutação; se falhar, regista-se erro no log com `requestId` e a resposta mantém-se (a mutação já foi aplicada) |
| Auditoria | `audit_logs`: `issue.created`, `issue.updated`, `comment.created`, `comment.updated`, `comment.deleted` com `entityType`/`entityId`/`projectId` em `details` |
| Consulta de auditoria | `GET /api/audit-logs` com `audit:read` (Admin), filtros `entityType`, `entityId`, `actorId`, `action`, intervalo de datas, paginado (`createdAt` desc) |

### Contratos API

| Método | Endpoint | Resposta |
|--------|----------|----------|
| GET | `/api/issues/{id}/comments?page=&pageSize=` | `Page<Comment>` por `createdAt` asc, com `author` resumido |
| POST | `/api/issues/{id}/comments` | 201 + `Comment` |
| PATCH | `/api/issues/{id}/comments/{commentId}` | `Comment` |
| DELETE | `/api/issues/{id}/comments/{commentId}` | 204 |
| GET | `/api/issues/{id}/history?page=&pageSize=` | `Page<HistoryEvent>` por `createdAt` desc, com `actor` |
| GET | `/api/audit-logs?…` | `Page<AuditLog>` |

## Implementation

### Phase 1: Testes

| Action | File | Details |
|--------|------|---------|
| Create | `backend/tests/test_issue_comments.py` | CRUD de comentários, permissões (autor/lead/admin), soft delete, projeto arquivado, paginação |
| Create | `backend/tests/test_issue_history.py` | Eventos de criação e alteração com diff correto, ordem, sem eventos quando nada muda, auditoria escrita, `GET /audit-logs` só para admin e com filtros |

### Phase 2: Backend

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/repositories/issue_comments.py` | Inserção, listagem paginada, edição, soft delete |
| Create | `backend/app/repositories/issue_history.py` | `record(issue_id, project_id, actor_id, type, changes)`, listagem paginada |
| Modify | `backend/app/repositories/audit.py` | `search(filter, skip, limit)` + `count` |
| Create | `backend/app/services/issue_history.py` | `diff_issue(before, after)` e escrita resiliente |
| Create | `backend/app/services/issue_comments.py` | Regras dos comentários |
| Modify | `backend/app/services/issues.py` | Regista histórico e auditoria em create/update |
| Create | `backend/app/schemas/{comments,history,audit}.py` | DTOs |
| Modify | `backend/app/api/routes/issues.py` | Endpoints de comentários e histórico |
| Create | `backend/app/api/routes/audit.py` | `GET /audit-logs` |
| Modify | `backend/app/api/router.py` | Incluir `audit.router` |
| Modify | `database/indexes/indexes.json` | `issue_comments_issueId_createdAt` |

### Phase 3: Frontend

| Action | File | Details |
|--------|------|---------|
| Create | `frontend/src/features/issues/IssueComments.tsx` | Lista, novo comentário, editar/remover (conforme permissões), Markdown |
| Create | `frontend/src/features/issues/IssueHistory.tsx` | Linha temporal legível ("Ana alterou Estado de A fazer para Em progresso") |
| Modify | `frontend/src/features/issues/IssueDetailPage.tsx` | Separadores Comentários / Histórico |
| Create | `frontend/src/features/admin/AuditLogPage.tsx` | Tabela paginada com filtros (só com `audit:read`) |
| Modify | `frontend/src/app/router.tsx`, `frontend/src/app/layout/AppLayout.tsx` | Rota `/admin/audit` e entrada de navegação condicional |
| Create | `frontend/src/services/{comments,audit}.ts` | Cliente |
| Create | `frontend/src/features/issues/comments.test.tsx` | Comentar, editar, remover, histórico |

- [ ] `pytest`, `ruff`, `npm run typecheck && npm run lint && npm test` passam

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/tests/test_issue_comments.py`, `backend/tests/test_issue_history.py` | Create | Testes |
| `backend/app/repositories/{issue_comments,issue_history}.py` | Create | Persistência |
| `backend/app/repositories/audit.py` | Modify | Consulta |
| `backend/app/services/{issue_comments,issue_history}.py` | Create | Regras |
| `backend/app/services/issues.py` | Modify | Histórico e auditoria |
| `backend/app/schemas/{comments,history,audit}.py` | Create | DTOs |
| `backend/app/api/routes/{issues,audit}.py`, `backend/app/api/router.py` | Create/Modify | API |
| `database/indexes/indexes.json` | Modify | Índices |
| `frontend/src/features/issues/*`, `frontend/src/features/admin/AuditLogPage.tsx` | Create/Modify | UI |
| `frontend/src/services/{comments,audit}.ts` | Create | Cliente |
| `frontend/src/app/{router.tsx,layout/AppLayout.tsx}` | Modify | Rotas e navegação |
| `backend/README.md` | Modify | Documentação |
