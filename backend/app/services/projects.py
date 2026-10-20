"""Gestão de projetos e membros (DEV-009)."""

import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from app.core.errors import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.domain.permissions import Permission
from app.domain.projects import (
    DEFAULT_PROJECT_SETTINGS,
    ProjectStatus,
    can_manage_project,
    is_archived,
    normalize_project_key,
)
from app.domain.users import User, UserStatus
from app.repositories.audit import AuditLogRepository
from app.repositories.projects import ProjectKeyExistsError, ProjectRepository
from app.repositories.users import UserRepository
from app.schemas.auth import UserSummary
from app.schemas.common import PageParams
from app.schemas.projects import (
    MemberResponse,
    ProjectCreate,
    ProjectMembersResponse,
    ProjectResponse,
    ProjectSettings,
    ProjectUpdate,
)
from app.services.authorization import (
    accessible_projects_filter,
    ensure_project_access,
    ensure_project_manager,
)
from app.services.common import (
    date_to_datetime,
    datetime_to_date,
    jsonable,
    object_id_or_422,
)

PROJECT_SORT_FIELDS = {"name": "name", "key": "key", "updatedAt": "updatedAt"}

_TRACKED_FIELDS = (
    "name",
    "description",
    "status",
    "priority",
    "leadUserId",
    "startDate",
    "targetDate",
    "settings",
)


class ProjectService:
    def __init__(self, db: Database) -> None:
        self.projects = ProjectRepository(db)
        self.users = UserRepository(db)
        self.audit = AuditLogRepository(db)

    # Leitura -------------------------------------------------------------------------------

    def get_accessible(self, user: User, project_id: ObjectId) -> dict[str, Any]:
        return dict(ensure_project_access(user, self.projects.find_by_id(project_id)))

    def search(
        self,
        user: User,
        *,
        statuses: list[ProjectStatus],
        include_archived: bool,
        text: str | None,
        sort: list[tuple[str, int]],
        page: PageParams,
    ) -> tuple[list[ProjectResponse], int]:
        conditions: list[dict[str, Any]] = []
        access = accessible_projects_filter(user)
        if access:
            conditions.append(access)
        if statuses:
            conditions.append({"status": {"$in": [status.value for status in statuses]}})
        elif not include_archived:
            conditions.append({"status": {"$ne": ProjectStatus.ARCHIVED.value}})
        if text and text.strip():
            pattern = re.escape(text.strip())
            conditions.append(
                {
                    "$or": [
                        {"name": {"$regex": pattern, "$options": "i"}},
                        {"key": {"$regex": f"^{pattern}", "$options": "i"}},
                    ]
                }
            )
        query = {"$and": conditions} if conditions else {}
        documents = self.projects.search(query, sort=sort, skip=page.skip, limit=page.page_size)
        return self.to_responses(user, documents), self.projects.count(query)

    def members(self, user: User, project_id: ObjectId) -> ProjectMembersResponse:
        return self._members_response(user, self.get_accessible(user, project_id))

    # Escrita -------------------------------------------------------------------------------

    def create(self, user: User, data: ProjectCreate) -> ProjectResponse:
        if not user.has_permissions(Permission.PROJECTS_MANAGE):
            raise ForbiddenError("Não tem permissão para criar projetos")
        try:
            key = normalize_project_key(data.key)
        except ValueError as error:
            raise BusinessRuleError(str(error), field="key") from error
        self._validate_dates(data.start_date, data.target_date)

        lead_id = object_id_or_422(data.lead_user_id, "leadUserId") if data.lead_user_id else None
        if lead_id is None and not user.is_admin:
            lead_id = user.id
        if lead_id is not None:
            self._ensure_valid_lead(lead_id)

        member_ids = [object_id_or_422(value, "memberIds") for value in data.member_ids]
        if not user.is_admin:
            # Quem cria (Tech Lead) continua a ter acesso mesmo que indique outro responsável.
            member_ids.append(user.id)
        if lead_id is not None:
            member_ids.append(lead_id)
        member_ids = list(dict.fromkeys(member_ids))
        self._ensure_active_users(member_ids)

        settings = dict(DEFAULT_PROJECT_SETTINGS)
        if data.settings:
            settings["sprintDurationDays"] = data.settings.sprint_duration_days

        now = datetime.now(UTC)
        document: dict[str, Any] = {
            "key": key,
            "name": data.name.strip(),
            "description": data.description.strip(),
            "status": data.status,
            "priority": data.priority.value,
            "leadUserId": lead_id,
            "memberIds": member_ids,
            "startDate": date_to_datetime(data.start_date),
            "targetDate": date_to_datetime(data.target_date),
            "settings": settings,
            "archivedAt": None,
            "createdBy": user.id,
            "createdAt": now,
            "updatedAt": now,
            "version": 1,
        }
        if not document["name"]:
            raise BusinessRuleError("O nome é obrigatório", field="name")
        try:
            project = self.projects.create(document)
        except ProjectKeyExistsError as error:
            raise ConflictError(f"Já existe um projeto com a chave {key}", field="key") from error
        self._audit("project.created", user, project, now, {"key": key})
        return self.to_response(user, project)

    def update(self, user: User, project_id: ObjectId, data: ProjectUpdate) -> ProjectResponse:
        project = self._get_manageable(user, project_id)
        provided = data.model_fields_set - {"version"}
        changes: dict[str, Any] = {}

        if "name" in provided:
            name = (data.name or "").strip()
            if not name:
                raise BusinessRuleError("O nome é obrigatório", field="name")
            changes["name"] = name
        if "description" in provided:
            changes["description"] = (data.description or "").strip()
        if "status" in provided:
            if data.status is None:
                raise BusinessRuleError("Estado inválido", field="status")
            changes["status"] = data.status
        if "priority" in provided:
            if data.priority is None:
                raise BusinessRuleError("Prioridade inválida", field="priority")
            changes["priority"] = data.priority.value
        if "start_date" in provided:
            changes["startDate"] = date_to_datetime(data.start_date)
        if "target_date" in provided:
            changes["targetDate"] = date_to_datetime(data.target_date)
        if "settings" in provided and data.settings is not None:
            changes["settings"] = {
                **project.get("settings", DEFAULT_PROJECT_SETTINGS),
                "sprintDurationDays": data.settings.sprint_duration_days,
            }

        new_lead: ObjectId | None = None
        if "lead_user_id" in provided:
            new_lead = (
                object_id_or_422(data.lead_user_id, "leadUserId") if data.lead_user_id else None
            )
            if new_lead is None and not user.is_admin:
                raise BusinessRuleError("O projeto tem de ter um responsável", field="leadUserId")
            if new_lead is not None:
                self._ensure_valid_lead(new_lead)
            changes["leadUserId"] = new_lead

        start = changes.get("startDate", project.get("startDate"))
        target = changes.get("targetDate", project.get("targetDate"))
        self._validate_dates(datetime_to_date(start), datetime_to_date(target))

        diff = {
            field: {"from": jsonable(project.get(field)), "to": jsonable(value)}
            for field, value in changes.items()
            if field in _TRACKED_FIELDS and project.get(field) != value
        }
        if not diff:
            self._check_version(project, data.version)
            return self.to_response(user, project)

        now = datetime.now(UTC)
        updated = self.projects.update_versioned(
            project_id, data.version, now=now, set_fields=changes, add_member=new_lead
        )
        updated = self._require_updated(updated, project_id)
        self._audit("project.updated", user, updated, now, {"changes": diff})
        return self.to_response(user, updated)

    def archive(self, user: User, project_id: ObjectId, version: int) -> ProjectResponse:
        project = self._get_manageable(user, project_id, allow_archived=True)
        if is_archived(project):
            raise BusinessRuleError("O projeto já está arquivado")
        now = datetime.now(UTC)
        updated = self.projects.update_versioned(
            project_id,
            version,
            now=now,
            set_fields={
                "status": ProjectStatus.ARCHIVED.value,
                "statusBeforeArchive": project["status"],
                "archivedAt": now,
            },
        )
        updated = self._require_updated(updated, project_id)
        self._audit("project.archived", user, updated, now)
        return self.to_response(user, updated)

    def restore(self, user: User, project_id: ObjectId, version: int) -> ProjectResponse:
        project = self._get_manageable(user, project_id, allow_archived=True)
        if not is_archived(project):
            raise BusinessRuleError("O projeto não está arquivado")
        now = datetime.now(UTC)
        updated = self.projects.update_versioned(
            project_id,
            version,
            now=now,
            set_fields={
                "status": project.get("statusBeforeArchive") or ProjectStatus.ACTIVE.value,
                "archivedAt": None,
            },
        )
        updated = self._require_updated(updated, project_id)
        self._audit("project.restored", user, updated, now)
        return self.to_response(user, updated)

    def add_member(
        self, user: User, project_id: ObjectId, member_id: ObjectId, version: int
    ) -> ProjectMembersResponse:
        project = self._get_manageable(user, project_id)
        self._check_version(project, version)
        if member_id in project.get("memberIds", []):
            return self._members_response(user, project)
        self._ensure_active_users([member_id], field="userId")
        now = datetime.now(UTC)
        updated = self.projects.update_versioned(project_id, version, now=now, add_member=member_id)
        updated = self._require_updated(updated, project_id)
        self._audit("project.member_added", user, updated, now, {"userId": str(member_id)})
        return self._members_response(user, updated)

    def remove_member(
        self, user: User, project_id: ObjectId, member_id: ObjectId, version: int
    ) -> ProjectMembersResponse:
        project = self._get_manageable(user, project_id)
        self._check_version(project, version)
        if project.get("leadUserId") == member_id:
            raise BusinessRuleError("O responsável do projeto não pode ser removido dos membros")
        if member_id not in project.get("memberIds", []):
            return self._members_response(user, project)
        now = datetime.now(UTC)
        updated = self.projects.update_versioned(
            project_id, version, now=now, remove_member=member_id
        )
        updated = self._require_updated(updated, project_id)
        self._audit("project.member_removed", user, updated, now, {"userId": str(member_id)})
        return self._members_response(user, updated)

    # Conversão -----------------------------------------------------------------------------

    def to_response(self, user: User, project: dict[str, Any]) -> ProjectResponse:
        return self.to_responses(user, [project])[0]

    def to_responses(self, user: User, projects: Iterable[dict[str, Any]]) -> list[ProjectResponse]:
        projects = list(projects)
        leads = self.users.find_by_ids(
            [project["leadUserId"] for project in projects if project.get("leadUserId")]
        )
        return [self._build_response(user, project, leads) for project in projects]

    def _build_response(
        self, user: User, project: dict[str, Any], leads: dict[ObjectId, dict[str, Any]]
    ) -> ProjectResponse:
        lead = leads.get(project.get("leadUserId"))
        settings = {**DEFAULT_PROJECT_SETTINGS, **project.get("settings", {})}
        return ProjectResponse(
            id=str(project["_id"]),
            key=project["key"],
            name=project["name"],
            description=project.get("description", ""),
            status=ProjectStatus(project["status"]),
            priority=project.get("priority", "medium"),
            lead=UserSummary.from_document(lead) if lead else None,
            start_date=datetime_to_date(project.get("startDate")),
            target_date=datetime_to_date(project.get("targetDate")),
            member_count=len(project.get("memberIds", [])),
            settings=ProjectSettings(
                methodology=settings["methodology"],
                sprint_duration_days=settings["sprintDurationDays"],
                estimation_type=settings["estimationType"],
            ),
            created_at=project["createdAt"],
            updated_at=project["updatedAt"],
            archived_at=project.get("archivedAt"),
            version=project.get("version", 1),
            can_manage=can_manage_project(user, project) and not is_archived(project),
        )

    def _members_response(self, user: User, project: dict[str, Any]) -> ProjectMembersResponse:
        ids = list(project.get("memberIds", []))
        if project.get("leadUserId") and project["leadUserId"] not in ids:
            ids.append(project["leadUserId"])
        users = self.users.find_by_ids(ids)
        members = [
            MemberResponse(
                **UserSummary.from_document(users[member_id]).model_dump(),
                is_lead=member_id == project.get("leadUserId"),
            )
            for member_id in ids
            if member_id in users
        ]
        members.sort(key=lambda member: (not member.is_lead, member.name.lower()))
        return ProjectMembersResponse(
            version=project.get("version", 1),
            can_manage=can_manage_project(user, project) and not is_archived(project),
            members=members,
        )

    # Auxiliares ----------------------------------------------------------------------------

    def _get_manageable(
        self, user: User, project_id: ObjectId, *, allow_archived: bool = False
    ) -> dict[str, Any]:
        project = dict(ensure_project_manager(user, self.projects.find_by_id(project_id)))
        if is_archived(project) and not allow_archived:
            raise BusinessRuleError("O projeto está arquivado e só pode ser consultado")
        return project

    def _check_version(self, project: dict[str, Any], version: int) -> None:
        if project.get("version", 1) != version:
            raise ConflictError(
                "O projeto foi alterado entretanto. Recarregue e tente novamente.",
                currentVersion=project.get("version", 1),
            )

    def _require_updated(
        self, updated: dict[str, Any] | None, project_id: ObjectId
    ) -> dict[str, Any]:
        if updated is not None:
            return updated
        current = self.projects.find_by_id(project_id)
        if current is None:
            raise NotFoundError("Projeto não encontrado")
        raise ConflictError(
            "O projeto foi alterado entretanto. Recarregue e tente novamente.",
            currentVersion=current.get("version", 1),
        )

    def _ensure_active_users(self, user_ids: list[ObjectId], field: str = "memberIds") -> None:
        found = self.users.find_by_ids(user_ids)
        for user_id in user_ids:
            document = found.get(user_id)
            if document is None or document.get("status") != UserStatus.ACTIVE.value:
                raise BusinessRuleError(
                    "Utilizador inexistente ou inativo", field=field, userId=str(user_id)
                )

    def _ensure_valid_lead(self, lead_id: ObjectId) -> None:
        document = self.users.find_by_ids([lead_id]).get(lead_id)
        if document is None or document.get("status") != UserStatus.ACTIVE.value:
            raise BusinessRuleError("Responsável inexistente ou inativo", field="leadUserId")
        if not User.from_document(document).has_permissions(Permission.PROJECTS_MANAGE):
            raise BusinessRuleError(
                "O responsável tem de ser Tech Lead ou Administrador", field="leadUserId"
            )

    @staticmethod
    def _validate_dates(start: Any, target: Any) -> None:
        if start and target and target < start:
            raise BusinessRuleError(
                "A data prevista não pode ser anterior à data de início", field="targetDate"
            )

    def _audit(
        self,
        action: str,
        user: User,
        project: dict[str, Any],
        now: datetime,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.audit.record(
            action,
            now=now,
            actor_id=user.id,
            entity_type="project",
            entity_id=project["_id"],
            details={"projectKey": project["key"], **(details or {})},
        )
