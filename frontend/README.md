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
├── hooks/        # usePermission
├── lib/          # utilitários (cn, mensagens de erro)
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

## Projetos

| Rota | Página |
|------|--------|
| `/projects` | Lista paginada com pesquisa, filtro de estado e "incluir arquivados" |
| `/projects/new`, `/projects/:projectId/edit` | Formulário partilhado (react-hook-form + zod); a chave só é editável na criação |
| `/projects/:projectId` | Layout com cabeçalho (editar, arquivar/restaurar) e separadores: Resumo, Membros; os restantes aparecem desativados até serem implementados |
| `/projects/:projectId/members` | Membros; adicionar com pesquisa (`GET /api/users`) e remover (exceto o responsável) |

- As ações de gestão aparecem conforme `usePermission('projects:manage')` e o `canManage`
  devolvido pela API; a autorização é sempre validada no backend.
- `ApiError` expõe as extensões problem+json (`field`, `errors`, `currentVersion`):
  `fieldErrors()` mapeia erros por campo e um 409 mostra o aviso de edição concorrente.
- Os componentes `native-select`, `table`, `badge` e `textarea` em `src/components/ui` seguem o
  estilo shadcn; usa-se `<select>` nativo (acessível e testável em jsdom).

## Issues

| Rota | Página |
|------|--------|
| `/projects/:projectId/issues` | Separador "Issues": filtros (pesquisa com debounce, estado, prioridade, tipo, responsável, label, bloqueadas), ordenação por cabeçalho (`aria-sort`) e paginação; tudo guardado no URL (`useIssueSearchParams`) |
| `/projects/:projectId/issues/new` | Criação (react-hook-form + zod); QA só vê o tipo Bug |
| `/issues/:issueKey` | Detalhe: descrição Markdown, critérios, dependências, mudança de estado (só `allowedTransitions`), bloquear/desbloquear com motivo |
| `/issues/:issueKey/edit` | Edição (o tipo não muda); a lista de pais segue a hierarquia do backend (`canBeParent`) |

- `src/components/Markdown.tsx` usa `react-markdown` sem HTML bruto (`skipHtml`); links abrem
  em novo separador com `rel="noopener noreferrer"`.
- Mutações enviam `version`; um 409 mostra o aviso de edição concorrente.
- O detalhe tem os separadores "Comentários" (Markdown, edição pelo autor, remoção em dois
  passos, formulário só com `issues:comment`) e "Histórico" (alterações em texto legível;
  descrição/critérios só indicam que mudaram).
- Secção "Anexos" no detalhe (`IssueAttachments`): download, miniatura de imagens
  (`?inline=1`), upload com `issues:write` (limite de 20 MiB validado também no cliente) e
  remoção em dois passos quando `canDelete`. `apiFetch` não define `Content-Type` para `FormData`.

## Auditoria

`/admin/audit` (entrada "Auditoria" no menu só com `audit:read`): tabela paginada com filtros
por ação, entidade e intervalo de datas.

Novos componentes shadcn: `npx shadcn@latest add <componente>` — confirmar que os imports
usam `@/lib/utils` e que os ficheiros ficam em `src/components/ui`.
