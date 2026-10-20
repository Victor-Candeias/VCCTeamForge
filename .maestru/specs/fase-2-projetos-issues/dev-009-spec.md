---
maestru: "0.4"
type: work-spec
id: dev-009-spec
title: "DEV-009 - CRUD de projetos e associação de membros"
template: implementation-plan-v1
work-item: fase-2-projetos-issues/DEV-009
owner: developer
created: 2026-10-20
---

# DEV-009 - CRUD de projetos e associação de membros

## Overview

Gestão de projetos (README §4.2, §5.2, §6 e critérios do MVP em §12): listar, criar, editar, arquivar/restaurar projetos e associar utilizadores como membros. É a base do marco **M1** e pré-requisito do DEV-010, porque as issues dependem do projeto (`projectId`) e da sua chave (`key`, ex.: `DVC-125`). Reutiliza o RBAC e o `ensure_project_access` do DEV-006, a auditoria e os erros RFC 7807 do DEV-008.

### Regras de domínio

| Regra | Decisão |
|-------|---------|
| Quem vê | Admin vê todos; restantes perfis só projetos onde são `leadUserId` ou estão em `memberIds` (`accessible_projects_filter`). Projeto alheio → 404 |
| Quem cria | Permissão `projects:manage` (Admin, Tech Lead). Tech Lead que cria fica como responsável se não indicar outro |
| Quem edita / gere membros | Admin ou o `leadUserId` do projeto, com `projects:manage`. Outros membros → 403 |
| `key` | 2–10 caracteres `^[A-Z][A-Z0-9]{1,9}$`, normalizada para maiúsculas, única (índice `projects_key_unique` → 409). **Imutável** após criação (as chaves das issues dependem dela) |
| Estados | `active`, `on_hold`, `completed`, `archived`. `archived` só via endpoint de arquivo; guarda `archivedAt`/`statusBeforeArchive` |
| Arquivado | Só leitura: PATCH e alterações de membros → 422. Não apaga issues, sprints nem auditoria (README §5.6). Não há DELETE |
| Prioridade | `low`, `medium`, `high`, `critical` (default `medium`) |
| Datas | `startDate` e `targetDate` opcionais (UTC, só data); `targetDate >= startDate` |
| Responsável | `leadUserId` tem de ser utilizador ativo com `projects:manage`; é sempre incluído em `memberIds` |
| Membros | Utilizadores ativos; `$addToSet`/`$pull` atómicos; o responsável não pode ser removido (422) |
| Concorrência | Campo `version`; PATCH e operações de membros exigem `version` atual → 409 se divergir (`update_one` com filtro `{_id, version}` + `$inc`) |
| Auditoria | `project.created`, `project.updated` (campos alterados, antes/depois), `project.archived`, `project.restored`, `project.member_added`, `project.member_removed` |
| `settings` | Defaults do README §5.2 (`scrum`, 14 dias, `story_points`); só `sprintDurationDays` (1–60) editável nesta fase |

### Contratos API

| Método | Endpoint | Permissão | Resposta |
|--------|----------|-----------|----------|
| GET | `/api/projects?status=&q=&includeArchived=&page=&pageSize=&sort=` | `projects:read` | `{items, total, page, pageSize}`; `pageSize` ≤ 100, `sort` ∈ `name`, `key`, `updatedAt` (±) |
| POST | `/api/projects` | `projects:manage` | 201 + projeto |
| GET | `/api/projects/{id}` | `projects:read` + acesso | Projeto com `lead` e contagem de membros |
| PATCH | `/api/projects/{id}` | `projects:manage` + lead/admin | Projeto (body com `version`) |
| POST | `/api/projects/{id}/archive` · `/restore` | `projects:manage` + lead/admin | Projeto |
| GET | `/api/projects/{id}/members` | `projects:read` + acesso | `[{id, name, email, role, isLead}]` |
| POST | `/api/projects/{id}/members` | `projects:manage` + lead/admin | `{userId, version}` → lista atualizada |
| DELETE | `/api/projects/{id}/members/{userId}?version=` | `projects:manage` + lead/admin | Lista atualizada |
| GET | `/api/users?q=&limit=` | `projects:manage` ou `users:manage` | Utilizadores ativos `{id, name, email, role}` (máx. 20) para o seletor de membros |

IDs inválidos (não `ObjectId`) → 404. Todas as mutações passam pelo `verify_csrf` já existente no `api_router`.

## Implementation

### Phase 1: Domínio, schemas e testes (TDD)

#### Step 1.1: Testes backend

| Action | File | Details |
|--------|------|---------|
| Create | `backend/tests/test_projects.py` | Testes de integração (MongoDB 4.4, fixtures de `conftest.py` e helpers de login do `test_auth.py`): criar (201, `key` normalizada, duplicada → 409, inválida → 422, sem permissão → 403); listar (paginação, filtros, só projetos acessíveis, arquivados excluídos por omissão); obter (alheio → 404, ID inválido → 404); PATCH (lead/admin ok, membro → 403, `version` antiga → 409, `key` não editável, datas inválidas → 422); arquivar/restaurar (arquivado só leitura); membros (adicionar/remover, inativo → 422, remover lead → 422, idempotência, novo membro passa a ver o projeto); auditoria de cada mutação; CSRF obrigatório |
| Create | `backend/tests/test_project_domain.py` | Testes unitários sem BD: validação/normalização de `key`, datas, transições de estado |

#### Step 1.2: Domínio e DTOs

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/domain/projects.py` | `ProjectStatus`, `ProjectPriority`, `normalize_project_key`, `PROJECT_KEY_PATTERN`, `DEFAULT_PROJECT_SETTINGS`, `can_manage_project(user, project)` (admin ou lead com `projects:manage`) |
| Create | `backend/app/schemas/projects.py` | `ProjectCreate`, `ProjectUpdate` (campos opcionais + `version`, `extra="forbid"` para impedir `key`/`memberIds`), `ProjectResponse`, `ProjectListResponse`, `ProjectListQuery`, `MemberAdd`, `MemberResponse` — todos com `ApiModel` (camelCase) |
| Create | `backend/app/schemas/common.py` | `Page[T]` genérico (`items`, `total`, `page`, `pageSize`) reutilizável no DEV-011 |
| Modify | `backend/app/schemas/auth.py` | `UserSummary` (`id`, `name`, `email`, `role`) |

- [ ] Testes escritos e a falhar pelos motivos esperados

### Phase 2: Persistência e serviço

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/repositories/projects.py` | `ProjectRepository`: `create` (trata `DuplicateKeyError` → `ProjectKeyExistsError`), `find_by_id`, `list(filter, sort, skip, limit)` + `count`, `update_versioned(id, version, set)` → `None` se versão divergir, `add_member`/`remove_member` versionados (`$addToSet`/`$pull` + `$inc: {version: 1}` + `updatedAt`) |
| Modify | `backend/app/repositories/users.py` | `find_active_by_ids(ids)`, `search_active(q, limit)` (regex escapada sobre `name`/`normalizedEmail`, projeção sem `passwordHash`) |
| Create | `backend/app/services/projects.py` | `ProjectService`: aplica as regras da tabela acima, usa `ensure_project_access` para leitura e `can_manage_project` para escrita (403), distingue 404 (inexistente) de 409 (versão) com releitura, valida lead/membros ativos, regista auditoria com `actor_id` e diff |
| Modify | `backend/app/services/authorization.py` | `ensure_project_manager(user, project)` reutilizável pelos módulos seguintes |
| Modify | `database/indexes/indexes.json` | `projects_leadUserId` (`leadUserId: 1`) e `projects_status_name` (`status: 1, name: 1`) para listagem |

- [ ] `pytest tests/test_project_domain.py` passa
- [ ] `python -m app.cli migrate` cria os novos índices e é idempotente

### Phase 3: API

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/api/routes/projects.py` | Endpoints da tabela de contratos; `parse_object_id` → 404; `Cache-Control: no-store` nas leituras |
| Modify | `backend/app/api/routes/users.py` | `GET /users` (pesquisa para seletor de membros) |
| Modify | `backend/app/api/deps.py` | `parse_object_id` e `require_any_permission(*perms)` |
| Modify | `backend/app/api/router.py` | Incluir `projects.router` |

- [ ] `.venv/bin/pytest` (com `VCCTF_REQUIRE_MONGO=1` contra MongoDB 4.4) passa
- [ ] `.venv/bin/ruff check . && .venv/bin/ruff format --check .` passa
- [ ] Fluxo csrf → login → criar projeto → adicionar membro → login do membro → ver projeto verificado com curl

### Phase 4: Frontend

#### Step 4.1: Testes frontend

| Action | File | Details |
|--------|------|---------|
| Create | `frontend/src/features/projects/projects.test.tsx` | Lista com estados vazio/erro, botão "Novo projeto" só com `projects:manage`, validação do formulário (key maiúsculas, datas), conflito 409 mostra aviso para recarregar, gestão de membros (adicionar/remover, lead sem botão remover) |

#### Step 4.2: Serviços, páginas e navegação

| Action | File | Details |
|--------|------|---------|
| Create | `frontend/src/services/projects.ts` | Tipos `Project`, `ProjectMember`, `Page<T>` e chamadas `listProjects`, `getProject`, `createProject`, `updateProject`, `archiveProject`, `restoreProject`, `listMembers`, `addMember`, `removeMember`, `searchUsers` |
| Create | `frontend/src/features/projects/useProjects.ts` | Hooks TanStack Query com chaves `['projects', …]` e invalidação após mutações |
| Create | `frontend/src/features/projects/ProjectsPage.tsx` | Tabela paginada (chave, nome, estado, prioridade, responsável, datas), pesquisa, filtro de estado, toggle "incluir arquivados" |
| Create | `frontend/src/features/projects/ProjectForm.tsx` | react-hook-form + zod partilhado entre criar/editar; `key` só editável na criação |
| Create | `frontend/src/features/projects/ProjectDetailPage.tsx` | Cabeçalho com ações (editar, arquivar/restaurar), separadores Resumo e Membros ativos; Backlog, Sprints, Testes, Releases, Documentação e Métricas visíveis mas desativados ("disponível em breve") |
| Create | `frontend/src/features/projects/ProjectMembers.tsx` | Lista de membros e seletor com pesquisa (`GET /users`) |
| Create | `frontend/src/hooks/usePermissions.ts` | `hasPermission(user, perm)` a partir de `/users/me` |
| Create | `frontend/src/components/ui/{select,table,tabs,badge,dialog,textarea}.tsx` | Componentes shadcn necessários (`npx shadcn@latest add …`) |
| Modify | `frontend/src/app/router.tsx` | Rotas `/projects`, `/projects/new`, `/projects/:projectId`, `/projects/:projectId/edit` |
| Modify | `frontend/src/app/layout/AppLayout.tsx` | Entrada "Projetos" na navegação |
| Modify | `frontend/src/services/apiClient.ts` | Expor `status` 409/422 e `errors` do problem+json para mostrar mensagens por campo |

- [ ] `npm run typecheck && npm run lint && npm test` passam
- [ ] Verificação manual: Tech Lead cria projeto, adiciona Developer; Developer vê só esse projeto e não tem ações de edição

### Phase 5: Documentação e fecho

| Action | File | Details |
|--------|------|---------|
| Modify | `backend/README.md` | Endpoints de projetos/membros e regras de permissão |
| Modify | `frontend/README.md` | Páginas de projetos |
| Run | `maestru check` | Validar `.maestru/` e marcar DEV-009 como `done` |

- [ ] Critérios MVP "Criar, editar e arquivar projetos" e "Associar utilizadores a projetos" cumpridos

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/tests/test_projects.py` | Create | Testes de integração da API de projetos e membros |
| `backend/tests/test_project_domain.py` | Create | Testes unitários das regras de domínio |
| `backend/app/domain/projects.py` | Create | Estados, prioridades, chave e regras de gestão |
| `backend/app/schemas/projects.py` | Create | DTOs de projetos e membros |
| `backend/app/schemas/common.py` | Create | Paginação genérica |
| `backend/app/schemas/auth.py` | Modify | `UserSummary` |
| `backend/app/repositories/projects.py` | Create | Persistência com controlo otimista |
| `backend/app/repositories/users.py` | Modify | Pesquisa e validação de utilizadores ativos |
| `backend/app/services/projects.py` | Create | Regras de negócio e auditoria |
| `backend/app/services/authorization.py` | Modify | `ensure_project_manager` |
| `database/indexes/indexes.json` | Modify | Índices de listagem de projetos |
| `backend/app/api/deps.py` | Modify | `parse_object_id`, `require_any_permission` |
| `backend/app/api/routes/projects.py` | Create | Endpoints de projetos e membros |
| `backend/app/api/routes/users.py` | Modify | Pesquisa de utilizadores |
| `backend/app/api/router.py` | Modify | Registo das rotas |
| `frontend/src/features/projects/projects.test.tsx` | Create | Testes de UI |
| `frontend/src/services/projects.ts` | Create | Cliente da API de projetos |
| `frontend/src/services/apiClient.ts` | Modify | Erros de validação por campo |
| `frontend/src/hooks/usePermissions.ts` | Create | Verificação de permissões na UI |
| `frontend/src/components/ui/*.tsx` | Create | Componentes shadcn |
| `frontend/src/features/projects/*.tsx`, `useProjects.ts` | Create | Lista, formulário, detalhe e membros |
| `frontend/src/app/router.tsx` | Modify | Rotas de projetos |
| `frontend/src/app/layout/AppLayout.tsx` | Modify | Navegação |
| `backend/README.md`, `frontend/README.md` | Modify | Documentação |
