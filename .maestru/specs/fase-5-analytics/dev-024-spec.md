---
maestru: "0.4"
type: work-spec
id: dev-024-spec
title: "DEV-024 Spec — Exportação CSV/XLSX/PDF"
template: implementation-plan-v1
work-item: fase-5-analytics/DEV-024
owner: developer
created: 2026-10-20
---

# DEV-024 Exportação CSV/XLSX/PDF

## Overview

Exportação parametrizada das métricas do projeto (README §6 `GET /reports/export`; §9 "Exportações": CSV com tabelas e filtros ativos, XLSX com detalhe, várias folhas e resumos, PDF formatado com KPIs, gráficos e contexto). Reutiliza `ProjectMetricsService` (DEV-023) para acesso, validação dos filtros e conteúdo.

### Regras

| Regra | Decisão |
|-------|---------|
| Acesso | `reports:read` + acesso ao projeto (404 caso contrário); projetos arquivados também se exportam |
| Filtros | `projectId` e `format` obrigatórios; `sprintId`, `type`, `from`, `to` iguais às métricas (mesmos 422) |
| Issues | Do filtro e ativas no período: `createdAt < to+1` e (por concluir ou `completedAt >= from`); ordem por `number` |
| Volume | Geração síncrona até 5000 issues (`EXPORT_MAX_ISSUES`), senão 422 a pedir filtros. A geração assíncrona com retenção (README §9) fica para quando houver volumes que a justifiquem |
| CSV | Detalhe das issues; UTF-8 com BOM, `;`, decimais com vírgula (Excel pt-PT), datas UTC |
| XLSX | `openpyxl`: Resumo (contexto + KPIs), Issues e uma folha por tabela de métricas |
| PDF | `fpdf2` (puro Python, sem dependências de sistema): contexto, KPIs, barras de estados e velocity e as tabelas; fontes base Latin-1 (restantes caracteres → `?`) |
| Segurança | CSV/formula injection: prefixo `'` em texto começado por `= + - @ \t \r` no CSV; células XLSX sempre texto. `Content-Disposition: attachment`, `no-store`, `nosniff`. Auditoria `report.exported` |

## Implementation

### Phase 1: Backend

| Action | File | Details |
|--------|------|---------|
| Create | `backend/app/domain/exports.py` | `ExportFormat`, tipos MIME, limite, `neutralize_formula`, nome do ficheiro |
| Create | `backend/app/exports/report.py` | `ReportData`, etiquetas, contexto, KPIs e tabelas comuns aos formatos |
| Create | `backend/app/exports/cells.py` | Formatação pt-PT das células de texto |
| Create | `backend/app/exports/{csv,xlsx,pdf}_writer.py` | Escrita de cada formato |
| Create | `backend/app/services/report_exports.py` | `ReportExportService`: métricas, issues, limite, escrita e auditoria |
| Modify | `backend/app/api/routes/reports.py` | `GET /reports/export` |
| Modify | `backend/pyproject.toml`, `backend/requirements.txt` | `openpyxl`, `fpdf2` (lock regenerado) |
| Create | `backend/tests/test_report_exports.py` | CSV, XLSX, PDF, filtros, injeção de fórmulas, limite, acesso e auditoria |

### Phase 2: Frontend

| Action | File | Details |
|--------|------|---------|
| Modify | `frontend/src/services/apiClient.ts` | `apiDownload` (blob + nome do ficheiro, erros `ApiError`) e `saveDownloadedFile` |
| Modify | `frontend/src/services/analytics.ts` | `ExportFormat`, `exportReport` |
| Modify | `frontend/src/features/analytics/useAnalytics.ts` | `useExportReport` |
| Modify | `frontend/src/features/analytics/ProjectMetricsPage.tsx` | Botões "Exportar" CSV/XLSX/PDF com os filtros ativos e erro |
| Modify | `frontend/src/features/analytics/analytics.test.tsx` | Download com filtros e erro 422 |

- [x] `pytest`, `ruff`, `npm run typecheck && npm run lint && npm test` passam

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/domain/exports.py`, `backend/app/exports/*`, `backend/app/services/report_exports.py` | Create | Geração das exportações |
| `backend/app/api/routes/reports.py` | Modify | Endpoint |
| `backend/pyproject.toml`, `backend/requirements.txt` | Modify | Dependências |
| `frontend/src/services/*`, `frontend/src/features/analytics/*` | Modify | UI de exportação |
| `backend/README.md`, `frontend/README.md` | Modify | Documentação |
