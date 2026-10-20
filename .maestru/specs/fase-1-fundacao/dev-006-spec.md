---
maestru: "0.4"
type: work-spec
id: dev-006-spec
title: "DEV-006 Spec"
template: implementation-plan-v1
work-item: fase-1-fundacao/DEV-006
owner: developer
created: 2026-10-20
---

# DEV-006 - Login/logout, sessão e RBAC

## Overview

Autenticação local com sessões no servidor e autorização por perfil e por projeto (README §3 e §10): Argon2id, cookies `HttpOnly`/`SameSite`/`Secure`, proteção CSRF, rate limiting do login e auditoria. Inclui o frontend: página de login, guarda de rotas e logout. O comando `create-user` (o antigo `create-admin` do DEV-005) cria o primeiro administrador.

## Implementation

### Phase 1: Domínio e segurança

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/domain/permissions.py` | `Role`, `Permission`, `ROLE_PERMISSIONS` |
| Create | `backend/app/domain/users.py` | `User`, `UserStatus`, `normalize_email` |
| Create | `backend/app/core/security.py` | Argon2id (19 MiB, t=2, p=1), política 12–128, tokens e SHA-256 |
| Modify | `backend/pyproject.toml` | `argon2-cffi` |

### Phase 2: Persistência e serviços

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/repositories/{users,sessions,login_attempts,audit}.py` | Utilizadores, sessões (hash do token, inatividade + máximo absoluto), falhas de login e auditoria |
| Create | `backend/app/services/auth.py` | Login com rate limiting (email/IP, 429 + Retry-After), tempo constante, rehash, autenticação com expiração deslizante, logout |
| Create | `backend/app/services/users.py` | Criação de utilizadores com validação e auditoria |
| Create | `backend/app/services/authorization.py` | Acesso por projeto (admin, lead ou membro; caso contrário 404) e filtro de listagem |

### Phase 3: API e CLI

| Action | File | Details |
|--------|------|---------|
| Modify | `backend/app/api/deps.py` | `get_current_user`, `require_permissions`, `verify_csrf` (double submit + associado à sessão; não acede à BD em GET) |
| Create | `backend/app/api/cookies.py` | Cookies de sessão/CSRF |
| Create | `backend/app/api/routes/{auth,users}.py` | `/auth/csrf`, `/auth/login`, `/auth/logout`, `/users/me` |
| Modify | `backend/app/cli.py` | `create-user` (password por prompt ou `VCCTF_NEW_USER_PASSWORD`) |

### Phase 4: Frontend

| Action | File | Details |
|--------|------|---------|
| Modify | `frontend/src/services/apiClient.ts` | `X-CSRF-Token` em métodos não seguros |
| Create | `frontend/src/services/auth.ts` | `getCurrentUser`, `login`, `logout` |
| Create | `frontend/src/features/auth/*` | `LoginPage` (react-hook-form + zod), `RequireAuth`, `useCurrentUser`/`useLogout`, destino `next` seguro |
| Modify | `frontend/src/app/{router.tsx,queryClient.ts,layout/AppLayout.tsx}` | Rotas protegidas, 401 global, utilizador e logout no cabeçalho |

- [x] 80 testes backend (MongoDB 4.4.29) e 8 testes frontend passam
- [x] Fluxo csrf → login → me → logout verificado com curl contra a API real

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/domain/*.py` | Create | Perfis, permissões, utilizador |
| `backend/app/core/security.py` | Create | Passwords e tokens |
| `backend/app/core/config.py` | Modify | Cookies, sessão, rate limiting |
| `backend/app/repositories/*.py` | Create | Persistência |
| `backend/app/services/*.py` | Create | Autenticação e autorização |
| `backend/app/api/*` | Create/Modify | Endpoints e dependências |
| `backend/app/cli.py` | Modify | `create-user` |
| `backend/tests/test_auth.py` | Create | Testes |
| `frontend/src/**` | Create/Modify | Login e guarda de rotas |
| `backend/README.md`, `frontend/README.md`, `backend/.env.example` | Modify | Documentação |
