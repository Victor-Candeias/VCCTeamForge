---
maestru: "0.4"
type: work-spec
id: dev-028-spec
title: "DEV-028 Spec — Gestão de utilizadores na aplicação"
template: implementation-plan-v1
work-item: fase-7-evolucao/DEV-028
owner: developer
created: 2026-10-21
---

# DEV-028 Spec — Gestão de utilizadores na aplicação

## Overview

Gestão de utilizadores pela aplicação (README §3 e §4.8). Até agora só era possível criar utilizadores pela CLI (`create-user`). O Administrador (`users:manage`) passa a listar, criar, editar, ativar/desativar e redefinir passwords em **Administração → Utilizadores**.

### Regras

| Regra | Decisão |
|-------|---------|
| Vários utilizadores | Passa a haver vários utilizadores com perfis (Administrador, Tech Lead, Developer, QA). O DEV-027 continua válido: as regras de transição das issues não dependem do perfil |
| Remoção | Não se apagam utilizadores; desativam-se (`status=disabled`) para preservar o histórico, a auditoria e as referências |
| Auto-proteção | Um administrador não pode desativar a própria conta nem alterar o próprio perfil. Assim fica sempre pelo menos um administrador ativo |
| Sessões | Ao desativar, terminam todas as sessões do utilizador. Ao redefinir a password, terminam as sessões do utilizador (exceto a sessão atual, se for o próprio) |
| Email | Validado e normalizado; único (`users_normalizedEmail_unique`) → 409 com `field=email` |
| Password | Política existente (12 a 128 caracteres, Argon2id); nunca é devolvida nem registada |
| Concorrência | `version` com controlo otimista (409 com `currentVersion`), como nos projetos |
| Auditoria | `user.created` (`source=api`), `user.updated` (diff de `name`/`email`/`role`/`status`), `user.password_reset` |

### API

| Método | Endpoint | Notas |
|--------|----------|-------|
| `GET` | `/api/admin/users` | Filtros `q` (nome/email), `role`, `status`; `sort` `name`/`email`/`createdAt`/`lastLoginAt`; paginado |
| `POST` | `/api/admin/users` | `{email, name, role, password}` → 201 |
| `GET` | `/api/admin/users/{id}` | Detalhe |
| `PATCH` | `/api/admin/users/{id}` | `{version, name?, email?, role?, status?}` |
| `POST` | `/api/admin/users/{id}/password` | `{version, password}` |

## Implementation

### Phase 1: Backend

| Action | File | Details |
|--------|------|---------|
| Modify | `backend/app/repositories/users.py` | `search`, `count`, `update_versioned`, `find_by_id` (inclui versão) |
| Modify | `backend/app/repositories/sessions.py` | `delete_for_user(..., except_session_id)` |
| Modify | `backend/app/services/users.py` | Validação partilhada; `search`, `get`, `update`, `reset_password` |
| Create | `backend/app/schemas/users.py` | `UserCreate`, `UserUpdate`, `PasswordReset`, `UserAdminResponse` |
| Create | `backend/app/api/routes/admin_users.py` | Rotas protegidas por `users:manage` |
| Modify | `backend/app/api/router.py` | Registar o router |
| Create | `backend/tests/test_admin_users.py` | Permissões, criação, duplicados, edição, auto-proteção, desativação com fim de sessões, redefinição de password e conflito de versão |

### Phase 2: Frontend

| Action | File | Details |
|--------|------|---------|
| Create | `frontend/src/services/users.ts` | Tipos e chamadas à API |
| Create | `frontend/src/features/admin/useUsers.ts` | Hooks React Query |
| Create | `frontend/src/features/admin/UsersPage.tsx` | Lista com filtros, paginação e ativar/desativar |
| Create | `frontend/src/features/admin/UserForm.tsx` | Criar/editar e redefinir a password |
| Modify | `frontend/src/app/router.tsx`, `frontend/src/app/layout/AppLayout.tsx` | Rotas `/admin/users*` e navegação com `users:manage` |
| Create | `frontend/src/features/admin/users.test.tsx` | Lista, criação, validação e desativação |

### Phase 3: Documentação

| Action | File | Details |
|--------|------|---------|
| Modify | `backend/README.md` | Contratos da API de utilizadores |

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/repositories/users.py` | Modify | Pesquisa e atualização versionada |
| `backend/app/repositories/sessions.py` | Modify | Terminar sessões de um utilizador |
| `backend/app/services/users.py` | Modify | Regras de gestão |
| `backend/app/schemas/users.py` | Create | DTOs |
| `backend/app/api/routes/admin_users.py` | Create | Rotas |
| `backend/app/api/router.py` | Modify | Registo |
| `backend/tests/test_admin_users.py` | Create | Testes |
| `frontend/src/services/users.ts` | Create | Cliente API |
| `frontend/src/features/admin/*` | Create | Páginas e hooks |
| `frontend/src/app/router.tsx`, `AppLayout.tsx` | Modify | Rotas e navegação |
| `backend/README.md` | Modify | Documentação |
