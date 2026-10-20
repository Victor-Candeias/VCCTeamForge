---
maestru: "0.4"
type: work-spec
id: dev-023-spec
title: "DEV-023 Spec — Analytics e snapshots"
template: implementation-plan-v1
work-item: fase-5-analytics/DEV-023
owner: developer
created: 2026-10-20
---

# DEV-023 Analytics e snapshots

## Overview

Dashboard geral e métricas por projeto (README §4.1 "KPIs", "Sprint atual", "Gráficos: burndown, distribuição por estado, tendências", "Alertas", "Visão diferente por perfil"; §4.2 separador "métricas"; §4.7 "Filtros por projeto, sprint, período, tipo de issue", "Snapshots de métricas para relatórios históricos"; §5.1 `report_snapshots`; §6 `GET /dashboard/overview`; §9 métricas). Ativa o separador "Métricas" do projeto.

### Regras

| Regra | Decisão |
|-------|---------|
| Âmbito | Leitura com `reports:read`; só projetos acessíveis (membro, responsável ou admin). Projeto de outro utilizador → 404. O dashboard ignora projetos arquivados |
| KPIs | `openCount` = issues por concluir; `inProgressCount` = `in_progress` + `code_review` + `testing`; `blockedCount` = bloqueadas por concluir; `doneCount`; `criticalBugCount` = bugs `critical` por concluir; `testPassRate` = `pass / (pass + fail + blocked)` das execuções dos últimos 30 dias (`skipped`/`not_run` não contam) |
| Alertas | Bloqueadas há mais de 3 dias (`blockedAt`), sem atualização há mais de 14 dias (por concluir) e bugs críticos sem responsável; total e até 10 issues por alerta |
| Perfil | Resposta igual para todos; a UI ordena por perfil (gestão: alertas e sprints; QA: alertas com bugs críticos primeiro; restantes: o meu trabalho). `myWork` = issues por concluir atribuídas ao utilizador |
| Período | `from`/`to` (datas), por omissão últimos 90 dias; `from > to` ou mais de 366 dias → 422 `field=from` |
| Filtros | `sprintId` (do projeto, senão 422 `field=sprintId`) e `type` aplicam-se às métricas de issues (KPIs, distribuição, lead/cycle time, aging, workload); bug severity usa sempre bugs; QA, releases e tendências são do projeto. Não existem equipas no modelo (equipa = membros do projeto) |
| Lead/Cycle time | Issues concluídas (`completedAt`) no período. Lead = conclusão − criação; cycle = conclusão − primeira passagem a `in_progress` (histórico); dias com 1 casa decimal: média, mediana e percentil 85 |
| Aging | Issues por concluir por idade (0–7, 8–30, 31–90, > 90 dias) e as 10 mais antigas |
| Velocity | Até 10 sprints fechados no período (`closedAt`), ou só o sprint filtrado; média de velocidade e de previsibilidade |
| Release Quality | 10 releases mais recentes com issues concluídas, bugs conhecidos abertos, pass rate dos planos e `ready` (mesma avaliação da release) |
| Workload | Por responsável (e "sem responsável"): issues por concluir, em progresso, bloqueadas e SP em aberto. Sem métricas de desempenho individual (nada concluído por pessoa) |
| Snapshots | `report_snapshots` `{projectId, day, kpis, statusBreakdown, takenAt}`, um por projeto e dia (substituído). Gerados por `python -m app.cli report-snapshots` (timer systemd diário) ou `POST /reports/projects/{id}/snapshots` (`projects:manage` + gestor do projeto). As tendências usam estes snapshots |

## Implementation

### Phase 1: Backend

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/domain/analytics.py` | Limiares, intervalos de aging, estatísticas de duração e validação do período |
| Create | `backend/app/repositories/analytics.py` | Agregações sobre `issues`, `issue_history`, `test_runs` e `report_snapshots` |
| Create | `backend/app/schemas/analytics.py` | `DashboardOverview`, `ProjectMetrics`, `ReportSnapshot` |
| Create | `backend/app/services/analytics.py` | `DashboardService`, `ProjectMetricsService`, `ReportSnapshotService` |
| Modify | `backend/app/services/releases.py` | `quality_for` público (reutilizado nas métricas) |
| Modify | `backend/app/services/sprint_reports.py` | `velocity_entry(sprint)` de módulo (reutilizado na velocity) |
| Create | `backend/app/api/routes/dashboard.py` | `GET /dashboard/overview` |
| Modify | `backend/app/api/routes/reports.py` | `GET /reports/projects/{id}/metrics`, `POST /reports/projects/{id}/snapshots` |
| Modify | `backend/app/cli.py` | Comando `report-snapshots` |
| Create | `database/migrations/0009_report_snapshots.py` | Collection `report_snapshots` |
| Modify | `database/indexes/indexes.json` | `report_snapshots_projectId_day_unique` (o cycle time usa o índice existente de `issue_history` por issue) |
| Create | `deployment/systemd/VCCTeamForge-report-snapshots.{service,timer}` | Snapshot diário (23:50 UTC, `Persistent=true`) |
| Modify | `deployment/scripts/install.sh`, `deployment/scripts/deploy-local.sh` | Instalar e ativar o timer |
| Create | `backend/tests/test_analytics.py` | Overview, alertas, métricas, filtros, snapshots, permissões e CLI |

### Phase 2: Frontend

| Action | File | Details |
|--------|------|---------|
| Create | `frontend/src/services/analytics.ts` | Tipos e cliente da API |
| Create | `frontend/src/features/analytics/useAnalytics.ts` | Hooks React Query |
| Create | `frontend/src/features/analytics/AnalyticsShared.tsx` | KPIs, secções, barras de estado e tabela de issues |
| Create | `frontend/src/features/analytics/AnalyticsCharts.tsx` | Gráficos Recharts (tendência, estados, velocity), carregados com `React.lazy` |
| Create | `frontend/src/features/analytics/format.ts` | Formatadores de números, percentagens e dias |
| Modify | `frontend/src/features/dashboard/DashboardPage.tsx` | Overview com KPIs, sprints ativas, alertas, o meu trabalho, distribuição e tendência; ordem por perfil |
| Create | `frontend/src/features/analytics/ProjectMetricsPage.tsx` | Filtros, secções de métricas e "Gravar snapshot de hoje" |
| Modify | `frontend/src/features/projects/projectContext.ts` | Ativar o separador "Métricas" |
| Modify | `frontend/src/app/router.tsx` | Rota `projects/:projectId/metrics` |
| Create | `frontend/src/features/analytics/analytics.test.tsx` | Dashboard por perfil, métricas, filtros e snapshot |
| Modify | `frontend/src/features/projects/projects.test.tsx` | Separador "Métricas" ativo |

- [x] `pytest`, `ruff`, `npm run typecheck && npm run lint && npm test` passam

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/{domain,repositories,schemas,services,api}/…`, `backend/app/cli.py` | Create/Modify | API de analytics |
| `database/migrations/0009_report_snapshots.py`, `database/indexes/indexes.json` | Create/Modify | Collection e índices |
| `deployment/systemd/*`, `deployment/scripts/*`, `deployment/README.md` | Create/Modify | Snapshot diário |
| `frontend/src/features/analytics/*`, `frontend/src/features/dashboard/*`, `frontend/src/services/analytics.ts` | Create/Modify | UI de analytics |
| `backend/README.md`, `frontend/README.md` | Modify | Documentação |
