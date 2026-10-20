# VCCTeamForge — Frontend

SPA React + TypeScript + Vite. Em produção é publicada como ficheiros estáticos pelo Nginx
(sem processo Node.js).

## Stack

React, TypeScript, Vite, Tailwind CSS v4, shadcn/ui (Radix), TanStack Query, React Router,
React Hook Form + Zod, Vitest + Testing Library.

## Estrutura

```text
src/
├── app/          # providers, router, layout
├── components/   # componentes partilhados (ui/ = shadcn)
├── features/     # dashboard, projects, issues, sprints, testing, releases, reports
├── hooks/
├── lib/          # utilitários (cn)
├── services/     # cliente HTTP da API (/api)
└── test/         # setup e utilitários de teste
```

## Desenvolvimento

Requer Node.js 20.19+ (apenas para desenvolvimento/build).

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173, proxy /api -> http://127.0.0.1:5000
npm test
npm run lint
npm run build      # gera dist/ para o Nginx
```

O alvo do proxy pode ser alterado com `VITE_DEV_API_TARGET`.

Novos componentes shadcn: `npx shadcn@latest add <componente>` — confirmar que os imports
usam `@/lib/utils` e que os ficheiros ficam em `src/components/ui`.
