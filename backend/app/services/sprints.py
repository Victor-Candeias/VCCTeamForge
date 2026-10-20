"""Criação, listagem e edição de sprints (DEV-015) e totais de planeamento (DEV-016)."""

from collections.abc import Iterable
from datetime import UTC, date, datetime, time
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from app.core.errors import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.domain.projects import DEFAULT_PROJECT_SETTINGS, is_archived
from app.domain.sprints import (
    OPEN_STATUSES,
    SprintRuleError,
    SprintStatus,
    can_manage_sprints,
    default_end_date,
    duration_days,
    name_key,
    validate_capacity,
    validate_dates,
)
from app.domain.users import User
from app.repositories.audit import AuditLogRepository
from app.repositories.issues import IssueRepository
from app.repositories.projects import ProjectRepository
from app.repositories.sprints import SprintNameExistsError, SprintRepository
from app.schemas.common import PageParams
from app.schemas.sprints import (
    SprintCreate,
    SprintResponse,
    SprintResult,
    SprintRetrospective,
    SprintScope,
    SprintUpdate,
)
from app.services.authorization import ensure_project_access
from app.services.common import jsonable

SPRINT_SORT_FIELDS = {"startDate": "startDate", "name": "nameKey", "createdAt": "createdAt"}
DEFAULT_SPRINT_SORT = "-startDate"

_TRACKED_FIELDS = ("name", "goal", "startDate", "endDate", "capacityStoryPoints")


def _rule_error(error: SprintRuleError) -> BusinessRuleError:
    return BusinessRuleError(str(error), field=error.field)


def _result(value: dict[str, Any] | None) -> SprintResult | None:
    if not value:
        return None
    return SprintResult.model_validate(
        {**value, "carryOverSprintId": jsonable(value.get("carryOverSprintId"))}
    )


def _at(value: date) -> datetime:
    """O BSON não tem tipo data: guarda-se a meia-noite UTC."""
    return datetime.combine(value, time.min, tzinfo=UTC)


class SprintService:
    def __init__(self, db: Database) -> None:
        self.sprints = SprintRepository(db)
        self.projects = ProjectRepository(db)
        self.issues = IssueRepository(db)
        self.audit = AuditLogRepository(db)

    # Leitura -------------------------------------------------------------------------------

    def search(
        self,
        user: User,
        project_id: ObjectId,
        *,
        statuses: list[SprintStatus],
        sort: list[tuple[str, int]],
        page: PageParams,
    ) -> tuple[list[SprintResponse], int]:
        project = self._get_project(user, project_id)
        query: dict[str, Any] = {"projectId": project_id}
        if statuses:
            query["status"] = {"$in": [status.value for status in statuses]}
        documents = self.sprints.search(query, sort=sort, skip=page.skip, limit=page.page_size)
        return self.to_responses(user, project, documents), self.sprints.count(query)

    def get(self, user: User, sprint_id: ObjectId) -> SprintResponse:
        sprint, project = self._get_with_project(user, sprint_id)
        return self.to_response(user, project, sprint)

    # Escrita -------------------------------------------------------------------------------

    def create(self, user: User, data: SprintCreate) -> SprintResponse:
        if not can_manage_sprints(user):
            raise ForbiddenError("Não tem permissão para gerir sprints")
        project_id = self._project_id_or_422(data.project_id)
        project = self._get_project(user, project_id, field="projectId")
        self._ensure_writable_project(project)

        name = self._clean_name(data.name)
        settings = {**DEFAULT_PROJECT_SETTINGS, **project.get("settings", {})}
        end = data.end_date or default_end_date(data.start_date, settings["sprintDurationDays"])
        self._validate_dates(data.start_date, end)
        start_at, end_at = _at(data.start_date), _at(end)
        self._ensure_no_overlap(project_id, start_at, end_at)
        capacity = self._validate_capacity(data.capacity_story_points)

        now = datetime.now(UTC)
        document: dict[str, Any] = {
            "projectId": project_id,
            "name": name,
            "nameKey": name_key(name),
            "goal": data.goal.strip(),
            "status": SprintStatus.PLANNED.value,
            "startDate": start_at,
            "endDate": end_at,
            "capacityStoryPoints": capacity,
            "committedStoryPoints": None,
            "committedIssueCount": None,
            "startedAt": None,
            "closedAt": None,
            "createdBy": user.id,
            "createdAt": now,
            "updatedAt": now,
            "version": 1,
        }
        try:
            sprint = self.sprints.create(document)
        except SprintNameExistsError as error:
            raise self._duplicate_name(name) from error
        self._audit("sprint.created", user, project, sprint, now, {"name": name})
        return self.to_response(user, project, sprint)

    def update(self, user: User, sprint_id: ObjectId, data: SprintUpdate) -> SprintResponse:
        if not can_manage_sprints(user):
            raise ForbiddenError("Não tem permissão para gerir sprints")
        sprint, project = self._get_with_project(user, sprint_id)
        self._ensure_writable_project(project)
        status = SprintStatus(sprint["status"])
        if status is SprintStatus.CLOSED:
            raise BusinessRuleError("O sprint está fechado e só pode ser consultado")

        provided = data.model_fields_set - {"version"}
        changes: dict[str, Any] = {}
        if "name" in provided:
            changes["name"] = self._clean_name(data.name or "")
            changes["nameKey"] = name_key(changes["name"])
        if "goal" in provided:
            changes["goal"] = (data.goal or "").strip()
        if "capacity_story_points" in provided:
            changes["capacityStoryPoints"] = self._validate_capacity(data.capacity_story_points)

        current_start: date = sprint["startDate"].date()
        current_end: date = sprint["endDate"].date()
        start, end = current_start, current_end
        if "start_date" in provided:
            if data.start_date is None:
                raise BusinessRuleError("A data de início é obrigatória", field="startDate")
            if status is SprintStatus.ACTIVE and data.start_date != current_start:
                raise BusinessRuleError(
                    "A data de início de um sprint ativo não pode ser alterada", field="startDate"
                )
            start = data.start_date
        if "end_date" in provided:
            if data.end_date is None:
                raise BusinessRuleError("A data de fim é obrigatória", field="endDate")
            end = data.end_date
        if (start, end) != (current_start, current_end):
            self._validate_dates(start, end)
            start_at, end_at = _at(start), _at(end)
            self._ensure_no_overlap(project["_id"], start_at, end_at, exclude_id=sprint_id)
            changes["startDate"], changes["endDate"] = start_at, end_at

        diff = {
            field: {"from": jsonable(sprint.get(field)), "to": jsonable(value)}
            for field, value in changes.items()
            if field in _TRACKED_FIELDS and sprint.get(field) != value
        }
        if not diff:
            self._check_version(sprint, data.version)
            return self.to_response(user, project, sprint)

        now = datetime.now(UTC)
        try:
            updated = self.sprints.update_versioned(
                sprint_id, data.version, now=now, set_fields=changes
            )
        except SprintNameExistsError as error:
            raise self._duplicate_name(changes["name"]) from error
        updated = self._require_updated(updated, sprint_id)
        self._audit("sprint.updated", user, project, updated, now, {"changes": diff})
        return self.to_response(user, project, updated)

    # Conversão -----------------------------------------------------------------------------

    def to_response(
        self, user: User, project: dict[str, Any], sprint: dict[str, Any]
    ) -> SprintResponse:
        return self.to_responses(user, project, [sprint])[0]

    def to_responses(
        self, user: User, project: dict[str, Any], sprints: Iterable[dict[str, Any]]
    ) -> list[SprintResponse]:
        sprints = list(sprints)
        writable = can_manage_sprints(user) and not is_archived(project)
        totals = self.issues.sprint_totals([sprint["_id"] for sprint in sprints])
        responses = []
        for sprint in sprints:
            start: date = sprint["startDate"].date()
            end: date = sprint["endDate"].date()
            responses.append(
                SprintResponse(
                    id=str(sprint["_id"]),
                    project_id=str(sprint["projectId"]),
                    name=sprint["name"],
                    goal=sprint.get("goal", ""),
                    status=SprintStatus(sprint["status"]),
                    start_date=start,
                    end_date=end,
                    duration_days=duration_days(start, end),
                    capacity_story_points=sprint.get("capacityStoryPoints"),
                    scope=SprintScope(**totals.get(sprint["_id"], {})),
                    committed_story_points=sprint.get("committedStoryPoints"),
                    committed_issue_count=sprint.get("committedIssueCount"),
                    started_at=sprint.get("startedAt"),
                    closed_at=sprint.get("closedAt"),
                    result=_result(sprint.get("result")),
                    retrospective=(
                        SprintRetrospective.model_validate(sprint["retrospective"])
                        if sprint.get("retrospective")
                        else None
                    ),
                    created_at=sprint["createdAt"],
                    updated_at=sprint["updatedAt"],
                    version=sprint.get("version", 1),
                    can_edit=writable and sprint["status"] != SprintStatus.CLOSED,
                )
            )
        return responses

    # Auxiliares ----------------------------------------------------------------------------

    @staticmethod
    def _project_id_or_422(value: str) -> ObjectId:
        if not ObjectId.is_valid(value):
            raise BusinessRuleError("Identificador inválido em projectId", field="projectId")
        return ObjectId(value)

    def _get_project(
        self, user: User, project_id: ObjectId, *, field: str | None = None
    ) -> dict[str, Any]:
        project = self.projects.find_by_id(project_id)
        try:
            return dict(ensure_project_access(user, project))
        except NotFoundError as error:
            if field:
                raise BusinessRuleError("Projeto inexistente ou sem acesso", field=field) from error
            raise

    def _get_with_project(
        self, user: User, sprint_id: ObjectId
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        sprint = self.sprints.find_by_id(sprint_id)
        if sprint is None:
            raise NotFoundError("Sprint não encontrado")
        try:
            project = self._get_project(user, sprint["projectId"])
        except NotFoundError as error:
            raise NotFoundError("Sprint não encontrado") from error
        return sprint, project

    @staticmethod
    def _ensure_writable_project(project: dict[str, Any]) -> None:
        if is_archived(project):
            raise BusinessRuleError("O projeto está arquivado e só pode ser consultado")

    @staticmethod
    def _clean_name(value: str) -> str:
        name = " ".join(value.split())
        if not name:
            raise BusinessRuleError("O nome é obrigatório", field="name")
        return name

    @staticmethod
    def _validate_dates(start: date, end: date) -> None:
        try:
            validate_dates(start, end)
        except SprintRuleError as error:
            raise _rule_error(error) from error

    @staticmethod
    def _validate_capacity(value: float | None) -> float | None:
        try:
            return validate_capacity(value)
        except SprintRuleError as error:
            raise _rule_error(error) from error

    def _ensure_no_overlap(
        self,
        project_id: ObjectId,
        start: datetime,
        end: datetime,
        *,
        exclude_id: ObjectId | None = None,
    ) -> None:
        other = self.sprints.find_overlapping(
            project_id,
            start=start,
            end=end,
            statuses=[status.value for status in OPEN_STATUSES],
            exclude_id=exclude_id,
        )
        if other is not None:
            raise BusinessRuleError(
                f"As datas sobrepõem-se ao sprint {other['name']}",
                field="startDate",
                sprintId=str(other["_id"]),
            )

    @staticmethod
    def _duplicate_name(name: str) -> ConflictError:
        return ConflictError(f"Já existe um sprint com o nome {name} neste projeto", field="name")

    def _check_version(self, sprint: dict[str, Any], version: int) -> None:
        if sprint.get("version", 1) != version:
            raise ConflictError(
                "O sprint foi alterado entretanto. Recarregue e tente novamente.",
                currentVersion=sprint.get("version", 1),
            )

    def _require_updated(
        self, updated: dict[str, Any] | None, sprint_id: ObjectId
    ) -> dict[str, Any]:
        if updated is not None:
            return updated
        current = self.sprints.find_by_id(sprint_id)
        if current is None:
            raise NotFoundError("Sprint não encontrado")
        raise ConflictError(
            "O sprint foi alterado entretanto. Recarregue e tente novamente.",
            currentVersion=current.get("version", 1),
        )

    def _audit(
        self,
        action: str,
        user: User,
        project: dict[str, Any],
        sprint: dict[str, Any],
        now: datetime,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.audit.record(
            action,
            now=now,
            actor_id=user.id,
            entity_type="sprint",
            entity_id=sprint["_id"],
            details={"projectKey": project["key"], **(details or {})},
        )
