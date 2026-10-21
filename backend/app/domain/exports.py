"""Regras das exportações de relatórios (README §9 "Exportações")."""

import re
from datetime import date
from enum import StrEnum

# Exportação síncrona: acima deste número de issues pede-se para filtrar.
EXPORT_MAX_ISSUES = 5000

# Células começadas por estes caracteres são interpretadas como fórmulas por folhas de cálculo
# (CSV/formula injection, OWASP).
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class ExportFormat(StrEnum):
    CSV = "csv"
    XLSX = "xlsx"
    PDF = "pdf"


MEDIA_TYPES = {
    ExportFormat.CSV: "text/csv; charset=utf-8",
    ExportFormat.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ExportFormat.PDF: "application/pdf",
}


def neutralize_formula(value: str) -> str:
    """Prefixa com `'` o texto que uma folha de cálculo executaria como fórmula."""
    return f"'{value}" if value.startswith(_FORMULA_PREFIXES) else value


def export_filename(project_key: str, export_format: ExportFormat, today: date) -> str:
    key = re.sub(r"[^A-Za-z0-9_-]", "", project_key) or "projeto"
    return f"vccteamforge-{key}-metricas-{today.isoformat()}.{export_format.value}"
