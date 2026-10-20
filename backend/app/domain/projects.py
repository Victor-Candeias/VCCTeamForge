"""Regras de domínio dos projetos (README §4.2 e §5.2)."""

import re
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from app.domain.permissions import Permission
from app.domain.users import User

PROJECT_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")

SPRINT_DURATION_MIN_DAYS = 1
SPRINT_DURATION_MAX_DAYS = 60


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    ARCHIVED = "archived"


# "archived" só é atingido pelo endpoint de arquivo, nunca por edição direta.
EDITABLE_STATUSES = frozenset(
    {ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD, ProjectStatus.COMPLETED}
)

DEFAULT_PROJECT_SETTINGS: dict[str, Any] = {
    "methodology": "scrum",
    "sprintDurationDays": 14,
    "estimationType": "story_points",
}


def normalize_project_key(key: str) -> str:
    """Chave em maiúsculas (ex.: ``dvc`` → ``DVC``). Lança ``ValueError`` se for inválida."""
    normalized = key.strip().upper()
    if not PROJECT_KEY_PATTERN.match(normalized):
        raise ValueError(
            "A chave tem de ter 2 a 10 caracteres (letras e números), a começar por uma letra"
        )
    return normalized


def is_archived(project: Mapping[str, Any]) -> bool:
    return project.get("status") == ProjectStatus.ARCHIVED


def is_project_lead(user: User, project: Mapping[str, Any]) -> bool:
    return project.get("leadUserId") == user.id


def can_manage_project(user: User, project: Mapping[str, Any]) -> bool:
    """Editar o projeto e gerir membros: administrador ou responsável com ``projects:manage``."""
    if not user.has_permissions(Permission.PROJECTS_MANAGE):
        return False
    return user.is_admin or is_project_lead(user, project)
