---
maestru: "0.4"
type: work-spec
id: dev-029-spec
title: "DEV-029 Spec"
template: implementation-plan-v1
work-item: fase-7-evolucao/DEV-029
owner: developer
created: 2026-10-21
---

# DEV-029 Spec

## Overview

Dar à aplicação um aspeto mais profissional e consistente, ao estilo das ferramentas de gestão de trabalho (Linear/Jira), sem alterar funcionalidades.

Pressupostos (não há cores de marca definidas):

- A cor da marca é índigo/azul (`--primary`). Os neutros são frios (slate) e o fundo da aplicação é ligeiramente acinzentado, com cartões brancos.
- Mantêm-se os componentes próprios estilo shadcn em `src/components/ui`. Não se adiciona nenhuma biblioteca nova.
- O modo escuro fica com tokens coerentes (classe `.dark`), mas sem seletor na UI, porque não é prioritário.
- Os nomes acessíveis de links e botões não mudam, para os testes continuarem válidos.

## Implementation

### Fase 1 — Tema

- `src/index.css`:
  - Paleta índigo e neutros slate.
  - Cores de gráfico distintas (`--chart-1..5`) e novos tokens `--success` e `--warning`.
  - Tokens da barra lateral.
  - Base tipográfica: `antialiased`, títulos `h1` com `tracking-tight`.
  - Scrollbar discreta e `::selection`.
- Favicon e logótipo próprios: `public/favicon.svg` e o componente `BrandLogo`.

### Fase 2 — Layout

- `AppLayout`: barra lateral fixa (desktop) com logótipo, navegação com ícones lucide e estado ativo destacado.
- Bloco do utilizador no fundo da barra lateral, com avatar de iniciais, nome, perfil e o botão "Terminar sessão".
- Em mobile há uma barra superior com um botão que abre e fecha a barra lateral em overlay. A navegação é renderizada uma única vez.
- Área de conteúdo com `max-w-7xl` e padding responsivo.

### Fase 3 — Componentes e páginas

- Cartões com sombra subtil e borda.
- Tabelas com cabeçalho em fundo `muted`, texto em maiúsculas pequenas e linhas mais espaçadas.
- Inputs, selects e botões com altura de 36px (`h-9`).
- Badge `success`/`warning`.
- Login em duas colunas: painel da marca com gradiente à esquerda e formulário à direita; em mobile mostra só o formulário.
- Gráficos Recharts sem cores hexadecimais fixas: passam a usar tokens (`--destructive`, `--warning`, `--chart-*`).
- `ProjectLayout`: tabs com o estilo novo.

### Fase 4 — Validação

- `tsc -b`, `oxlint`, `vitest run` e `vite build`.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| frontend/src/index.css | modify | Tokens do tema e estilos base |
| frontend/public/favicon.svg | modify | Favicon da marca |
| frontend/src/components/BrandLogo.tsx | create | Logótipo reutilizável |
| frontend/src/app/layout/AppLayout.tsx | modify | Barra lateral, utilizador, responsivo |
| frontend/src/components/ui/card.tsx | modify | Sombra e borda |
| frontend/src/components/ui/table.tsx | modify | Cabeçalho e espaçamento |
| frontend/src/components/ui/button.tsx | modify | Alturas e sombra |
| frontend/src/components/ui/input.tsx | modify | Altura e fundo |
| frontend/src/components/ui/native-select.tsx | modify | Altura e fundo |
| frontend/src/components/ui/textarea.tsx | modify | Fundo |
| frontend/src/components/ui/badge.tsx | modify | Variantes success e warning |
| frontend/src/features/auth/LoginPage.tsx | modify | Login em duas colunas |
| frontend/src/features/projects/ProjectLayout.tsx | modify | Tabs |
| frontend/src/features/analytics/AnalyticsCharts.tsx | modify | Cores por tokens |
| frontend/src/features/sprints/SprintDashboardPage.tsx | modify | Cores por tokens |
| frontend/src/features/issues/IssueBadges.tsx | modify | Estados das issues com cores semânticas |
| frontend/src/features/projects/ProjectBadges.tsx | modify | Estado e prioridade com cores semânticas |
| frontend/src/features/releases/ReleaseShared.tsx | modify | Estados das releases com cores semânticas |
| frontend/src/features/testing/TestingShared.tsx | modify | Resultados das execuções de testes por tokens |
| frontend/src/features/admin/UsersPage.tsx | modify | Estado do utilizador com badge success |
