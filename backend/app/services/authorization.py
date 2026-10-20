"""Autorização por projeto: além da permissão do perfil, é preciso ser membro do projeto.

Administradores acedem a todos os projetos. Para não revelar a existência de projetos alheios,
o acesso negado é reportado como 404.
"""

from collections.abc import Mapping
from typing import Any

from app.core.errors import NotFoundError
from app.domain.users import User


def can_access_project(user: User, project: Mapping[str, Any]) -> bool:
    if user.is_admin:
        return True
    return project.get("leadUserId") == user.id or user.id in project.get("memberIds", [])


def ensure_project_access(user: User, project: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if project is None or not can_access_project(user, project):
        raise NotFoundError("Projeto não encontrado")
    return project


def accessible_projects_filter(user: User) -> dict[str, Any]:
    """Filtro MongoDB para listar apenas os projetos visíveis ao utilizador."""
    if user.is_admin:
        return {}
    return {"$or": [{"memberIds": user.id}, {"leadUserId": user.id}]}
