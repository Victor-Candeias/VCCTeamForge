---
maestru: "0.4"
type: work-spec
id: dev-019-spec
title: "DEV-019 - Dashboard de sprint e burndown"
template: implementation-plan-v1
work-item: fase-3-scrum/DEV-019
owner: developer
created: 2026-10-20
---

# DEV-019 - Dashboard de sprint e burndown

## Overview

Dashboard de sprint (README §4.4 "Quadro Scrum, progresso, burndown e capacidade", §6 `GET /reports/sprints/{id}`, §9 Burndown/Velocity/Predictability e critério MVP "Dashboard da sprint com KPIs"). Qualquer membro do projeto consulta os KPIs, o burndown, a distribuição por estado, os bloqueios e a velocidade dos últimos sprints. O burndown assenta em snapshots diários gravados quando o âmbito ou o progresso mudam.

### Regras

| Regra | Decisão |
|-------|---------|
| Endpoint | `GET /api/reports/sprints/{id}` → `SprintReport`; `reports:read` + acesso ao projeto (404 sem acesso); `Cache-Control: no-store` |
| Estado | Só sprints iniciados (`active`/`closed`); sprint `planned` → 422 `field=status` |
| Snapshots diários | `sprint_snapshots` `kind: "daily"`, um por dia (upsert por `day`, último estado do dia). Gravados no início, ao associar/remover issues de um sprint ativo, quando uma issue de um sprint ativo muda `status` ou `storyPoints`, e no fecho (estado antes do transporte) |
| Falhas | O snapshot diário é best-effort: erros do MongoDB ficam no log e não fazem falhar o pedido |
| Dados atuais | Sprint ativo: issues atuais; sprint fechado: snapshot de fecho |
| KPIs | Compromisso (issues/SP), âmbito atual, concluídas, SP restantes, progresso % (SP concluídos/âmbito; `null` sem SP), dias totais/decorridos/restantes, bloqueadas, adicionadas/retiradas desde o início |
| Burndown | Um ponto por dia de `min(startDate, dia do início)` a `max(endDate, hoje/dia do fecho)`: `ideal` linear do compromisso em `startDate` a 0 em `endDate`; `remaining` e `scope` do último snapshot diário até esse dia (dia atual de um sprint ativo = dados atuais); dias futuros ou anteriores ao primeiro snapshot → `null` |
| Distribuição | Issues e SP por estado (`todo` → `done`) |
| Bloqueios | Issues bloqueadas (chave, título, estado, motivo, desde); num sprint fechado vêm do snapshot de fecho |
| Velocidade | Até 5 sprints fechados do projeto com início ≤ ao do sprint: compromisso, concluídos, concluídos do compromisso, previsibilidade %; média dos concluídos |
| Frontend | Página `sprints/:sprintId/dashboard` com cartões de KPI, burndown (Recharts, definido no README §2), distribuição por estado, bloqueios e velocidade; ligação "Ver dashboard" no detalhe de sprints iniciados; rota carregada com `lazy` para o Recharts não entrar no bundle inicial |

## Implementation

### Phase 1 — Backend

- [x] Snapshots: `blocked` nos itens; `DailySnapshotRecorder` best-effort
- [x] Ganchos: início, associar/remover (sprint ativo), `IssueService.apply_update` (status/storyPoints), fecho
- [x] Schemas `schemas/reports.py` e `SprintReportService` (KPIs, burndown, distribuição, bloqueios, velocidade)
- [x] Router `reports` com `GET /api/reports/sprints/{id}`
- [x] Testes em `tests/test_sprint_reports.py`

### Phase 2 — Frontend

- [x] Dependência `recharts`
- [x] Serviço `services/reports.ts` e hook `useSprintReport`
- [x] `SprintDashboardPage` e rota; ligação no detalhe do sprint
- [x] Testes vitest

### Phase 3 — Documentação

- [x] READMEs do backend e do frontend

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/services/sprint_snapshots.py` | Modify | `blocked` e `DailySnapshotRecorder` |
| `backend/app/services/sprint_planning.py` | Modify | Snapshot diário ao associar/remover |
| `backend/app/services/sprint_lifecycle.py` | Modify | Snapshot diário no início e no fecho |
| `backend/app/services/issues.py` | Modify | Snapshot diário ao mudar status/SP |
| `backend/app/schemas/reports.py` | Create | DTOs do relatório |
| `backend/app/services/sprint_reports.py` | Create | Cálculo do relatório |
| `backend/app/api/routes/reports.py`, `backend/app/api/router.py` | Create/Modify | Rota |
| `backend/tests/test_sprint_reports.py` | Create | Testes |
| `frontend/package.json` | Modify | `recharts` |
| `frontend/src/services/reports.ts` | Create | API |
| `frontend/src/features/sprints/SprintDashboardPage.tsx` | Create | Dashboard |
| `frontend/src/features/sprints/useSprints.ts` | Modify | Hook |
| `frontend/src/features/sprints/SprintDetailPage.tsx`, `frontend/src/app/router.tsx` | Modify | Ligação e rota |
| `frontend/src/features/sprints/sprints.test.tsx` | Modify | Testes |
| `backend/README.md`, `frontend/README.md` | Modify | Documentação |
