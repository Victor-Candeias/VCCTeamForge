---
maestru: "0.4"
type: work-spec
id: dev-002-spec
title: "DEV-002 - Frontend React/Vite/TypeScript"
template: implementation-plan-v1
work-item: fase-1-fundacao/DEV-002
owner: developer
created: 2026-10-20
---

# DEV-002 - Frontend React/Vite/TypeScript

## Overview

Cria a SPA do VCCTeamForge com a stack definida no README §2 (React, TypeScript, Vite, Tailwind, shadcn/ui, TanStack Query, React Hook Form, Zod), publicada como estáticos pelo Nginx (DEV-002).

## Implementation

### Phase 1: Scaffold e stack

| Action | File | Details |
|--------|------|---------|
| Run | `npm create vite -- --template react-ts` | Projeto base em `frontend/` |
| Run | `npm install ...` | TanStack Query, React Router, RHF, Zod, Tailwind v4, Vitest |
| Run | `npx shadcn init/add` | Tema e componentes button, card, input, label, alert |
| Modify | `frontend/vite.config.ts` | Tailwind, alias `@`, proxy `/api`, Vitest |

### Phase 2: Estrutura da aplicação

| Action | File | Details |
|--------|------|---------|
| Create | `frontend/src/app/*` | Providers, router, layout, 404 |
| Create | `frontend/src/services/apiClient.ts` | `fetch` com credenciais same-origin e erros tipados |
| Create | `frontend/src/features/dashboard/DashboardPage.tsx` | Estado da API via TanStack Query |
| Create | `frontend/src/features/*/` | Pastas por feature (README §7) |

- [x] `npm run typecheck`, `npm run lint`, `npm test` e `npm run build` passam
- [x] Proxy `/api` do Vite chega ao backend

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `frontend/package.json` | Create | Dependências e scripts |
| `frontend/vite.config.ts` | Create | Build, proxy e testes |
| `frontend/components.json` | Create | Configuração shadcn/ui |
| `frontend/src/**` | Create | Aplicação |
| `frontend/README.md` | Create | Instruções |
