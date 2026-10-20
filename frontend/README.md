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
├── features/     # auth, dashboard, projects, issues, sprints, testing, releases, reports
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

## Autenticação

- As rotas protegidas ficam dentro de `RequireAuth`. Sem sessão, o utilizador é enviado para
  `/login?next=<destino>`; só são aceites destinos internos.
- A sessão é um cookie `HttpOnly` gerido pelo backend; o frontend não guarda tokens.
  `useCurrentUser()` (query `['auth', 'me']`) devolve o utilizador ou `null`.
- `apiFetch` envia `X-CSRF-Token` (lido do cookie `vcctf_csrf`) em todos os métodos não seguros
  e obtém o token em `/api/auth/csrf` quando ainda não existe.
- Qualquer 401 limpa o utilizador em cache, e o `RequireAuth` redireciona para o login.

Novos componentes shadcn: `npx shadcn@latest add <componente>` — confirmar que os imports
usam `@/lib/utils` e que os ficheiros ficam em `src/components/ui`.
