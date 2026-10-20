"""Criação, consulta e edição de issues (DEV-010)."""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from app.core.errors import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.domain.common import PRIORITY_RANK, Priority
from app.domain.issues import (
    STATUS_RANK,
    IssueRuleError,
    IssueStatus,
    IssueType,
    allowed_transitions,
    can_create_issue_type,
    can_edit_issue,
    normalize_acceptance_criteria,
    normalize_labels,
    validate_parent,
    validate_story_points,
    validate_transition,
)
from app.domain.projects import is_archived
from app.domain.users import User, UserStatus
from app.repositories.counters import CounterRepository
from app.repositories.issues import IssueRepository
from app.repositories.projects import ProjectRepository
from app.repositories.users import UserRepository
from app.schemas.auth import UserSummary
from app.schemas.common import PageParams
from app.schemas.issues import Issue, IssueCreate, IssueRef, IssueSummary, IssueUpdate
from app.services.authorization import can_access_project, ensure_project_access
from app.services.common import date_to_datetime, datetime_to_date, jsonable, object_id_or_422

# Campos cujas alterações são reportadas (histórico/auditoria).
TRACKED_FIELDS = (
    "title",
    "description",
    "status",
    "priority",
    "assigneeId",
    "parentIssueId",
    "storyPoints",
    "labels",
    "acceptanceCriteria",
    "dependsOnIssueIds",
    "dueDate",
    "blocked",
    "blockReason",
)


def issue_counter_name(project_id: ObjectId) -> str:
    return f"issues:{project_id}"


class IssueService:
    def __init__(self, db: Database) -> None:
        self.issues = IssueRepository(db)
        self.projects = ProjectRepository(db)
        self.users = UserRepository(db)
        self.counters = CounterRepository(db)

    # Leitura -------------------------------------------------------------------------------

    def get_accessible(
        self, user: User, issue_id: ObjectId
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Devolve ``(issue, projeto)``; 404 se não existir ou o projeto não for acessível."""
        return self._with_project(user, self.issues.find_by_id(issue_id))

    def get_accessible_by_key(self, user: User, key: str) -> tuple[dict[str, Any], dict[str, Any]]:
        return self._with_project(user, self.issues.find_by_key(key.strip().upper()))

    def project_for_listing(self, user: User, project_id: ObjectId) -> dict[str, Any]:
        return dict(ensure_project_access(user, self.projects.find_by_id(project_id)))

    def search(
        self,
        query: dict[str, Any],
        *,
        sort: list[tuple[str, int]],
        page: PageParams,
    ) -> tuple[list[IssueSummary], int]:
        documents = self.issues.search(query, sort=sort, skip=page.skip, limit=page.page_size)
        return self.to_summaries(documents), self.issues.count(query)

    # Escrita -------------------------------------------------------------------------------

    def create(self, user: User, data: IssueCreate) -> Issue:
        project_id = object_id_or_422(data.project_id, "projectId")
        project = dict(ensure_project_access(user, self.projects.find_by_id(project_id)))
        if not can_create_issue_type(user, data.type):
            raise ForbiddenError("Não tem permissão para criar issues deste tipo")
        self._ensure_not_archived(project)

        title = data.title.strip()
        if not title:
            raise BusinessRuleError("O título é obrigatório", field="title")
        priority = data.priority or Priority.MEDIUM
        parent = self._load_parent(project, data.type, data.parent_issue_id, None)
        assignee_id = self._valid_assignee(project, data.assignee_id)
        try:
            story_points = validate_story_points(data.story_points)
            labels = normalize_labels(data.labels or [])
            criteria = normalize_acceptance_criteria(data.acceptance_criteria or [])
        except IssueRuleError as error:
            raise BusinessRuleError(str(error), field=error.field) from error
        dependencies = self._valid_dependencies(project, data.depends_on_issue_ids or [], None)

        number = self.counters.next_value(issue_counter_name(project_id))
        now = datetime.now(UTC)
        document: dict[str, Any] = {
            "projectId": project_id,
            "number": number,
            "key": f"{project['key']}-{number}",
            "type": data.type.value,
            "title": title,
            "description": (data.description or "").strip(),
            "status": IssueStatus.TODO.value,
            "statusRank": STATUS_RANK[IssueStatus.TODO],
            "priority": priority.value,
            "priorityRank": PRIORITY_RANK[priority],
            "assigneeId": assignee_id,
            "reporterId": user.id,
            "parentIssueId": parent["_id"] if parent else None,
            "sprintId": None,
            "storyPoints": story_points,
            "labels": labels,
            "acceptanceCriteria": criteria,
            "dependsOnIssueIds": dependencies,
            "dueDate": date_to_datetime(data.due_date),
            "blocked": False,
            "blockReason": None,
            "blockedAt": None,
            "completedAt": None,
            "createdBy": user.id,
            "createdAt": now,
            "updatedAt": now,
            "version": 1,
        }
        # Se o insert falhar depois de reservar o número fica um intervalo na numeração (aceite).
        issue = self.issues.create(document)
        return self.to_issue(user, issue, project)

    def update(self, user: User, issue_id: ObjectId, data: IssueUpdate) -> Issue:
        issue, project = self.get_accessible(user, issue_id)
        updated, _ = self.apply_update(user, issue, project, data)
        return self.to_issue(user, updated, project)

    def apply_update(
        self,
        user: User,
        issue: dict[str, Any],
        project: dict[str, Any],
        data: IssueUpdate,
    ) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        """Valida e grava a alteração; devolve a issue atualizada e o diff dos campos alterados."""
        if not can_edit_issue(user, issue):
            raise ForbiddenError("Só pode editar issues atribuídas a si ou que reportou")
        self._ensure_not_archived(project)
        changes = self._collect_changes(project, issue, data)
        diff = {
            field: {"from": jsonable(issue.get(field)), "to": jsonable(value)}
            for field, value in changes.items()
            if field in TRACKED_FIELDS and issue.get(field) != value
        }
        if not diff:
            self._check_version(issue, data.version)
            return issue, {}
        now = datetime.now(UTC)
        if "blocked" in diff:
            changes["blockedAt"] = now if changes["blocked"] else None
        if "status" in diff:
            done = changes["status"] == IssueStatus.DONE
            changes["completedAt"] = now if done else None
        updated = self.issues.update_versioned(
            issue["_id"], data.version, now=now, set_fields=changes
        )
        return self.require_updated(updated, issue["_id"]), diff

    # Conversão -----------------------------------------------------------------------------

    def to_summaries(self, issues: Iterable[dict[str, Any]]) -> list[IssueSummary]:
        issues = list(issues)
        users = self.users.find_by_ids([i["assigneeId"] for i in issues if i.get("assigneeId")])
        return [IssueSummary(**self._summary_fields(issue, users)) for issue in issues]

    def to_issue(self, user: User, issue: dict[str, Any], project: dict[str, Any]) -> Issue:
        users = self.users.find_by_ids(
            [value for value in (issue.get("assigneeId"), issue.get("reporterId")) if value]
        )
        related_ids = list(issue.get("dependsOnIssueIds", []))
        if issue.get("parentIssueId"):
            related_ids.append(issue["parentIssueId"])
        related = self.issues.find_many_by_ids(related_ids)
        parent = related.get(issue.get("parentIssueId"))
        reporter = users.get(issue.get("reporterId"))
        status = IssueStatus(issue["status"])
        editable = can_edit_issue(user, issue) and not is_archived(project)
        return Issue(
            **self._summary_fields(issue, users),
            project_key=project["key"],
            description=issue.get("description", ""),
            reporter=UserSummary.from_document(reporter) if reporter else None,
            parent=self._ref(parent) if parent else None,
            acceptance_criteria=issue.get("acceptanceCriteria", []),
            depends_on=[
                self._ref(related[dep_id])
                for dep_id in issue.get("dependsOnIssueIds", [])
                if dep_id in related
            ],
            block_reason=issue.get("blockReason"),
            blocked_at=issue.get("blockedAt"),
            completed_at=issue.get("completedAt"),
            created_at=issue["createdAt"],
            can_edit=editable,
            allowed_transitions=allowed_transitions(status) if editable else [],
        )

    @staticmethod
    def _summary_fields(
        issue: dict[str, Any], users: dict[ObjectId, dict[str, Any]]
    ) -> dict[str, Any]:
        assignee = users.get(issue.get("assigneeId"))
        return {
            "id": str(issue["_id"]),
            "project_id": str(issue["projectId"]),
            "key": issue["key"],
            "number": issue["number"],
            "type": issue["type"],
            "title": issue["title"],
            "status": issue["status"],
            "priority": issue["priority"],
            "assignee": UserSummary.from_document(assignee) if assignee else None,
            "story_points": issue.get("storyPoints"),
            "labels": issue.get("labels", []),
            "blocked": issue.get("blocked", False),
            "due_date": datetime_to_date(issue.get("dueDate")),
            "parent_issue_id": str(issue["parentIssueId"]) if issue.get("parentIssueId") else None,
            "sprint_id": str(issue["sprintId"]) if issue.get("sprintId") else None,
            "updated_at": issue["updatedAt"],
            "version": issue.get("version", 1),
        }

    @staticmethod
    def _ref(issue: dict[str, Any]) -> IssueRef:
        return IssueRef(
            id=str(issue["_id"]),
            key=issue["key"],
            title=issue["title"],
            type=issue["type"],
            status=issue["status"],
        )

    # Auxiliares ----------------------------------------------------------------------------

    def _with_project(
        self, user: User, issue: dict[str, Any] | None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        project = self.projects.find_by_id(issue["projectId"]) if issue else None
        if issue is None or project is None or not can_access_project(user, project):
            raise NotFoundError("Issue não encontrada")
        return issue, project

    def _collect_changes(
        self, project: dict[str, Any], issue: dict[str, Any], data: IssueUpdate
    ) -> dict[str, Any]:
        provided = data.model_fields_set - {"version"}
        changes: dict[str, Any] = {}
        try:
            if "title" in provided:
                title = (data.title or "").strip()
                if not title:
                    raise IssueRuleError("O título é obrigatório", "title")
                changes["title"] = title
            if "description" in provided:
                changes["description"] = (data.description or "").strip()
            if "priority" in provided:
                if data.priority is None:
                    raise IssueRuleError("Prioridade inválida", "priority")
                changes["priority"] = data.priority.value
                changes["priorityRank"] = PRIORITY_RANK[data.priority]
            if "status" in provided:
                if data.status is None:
                    raise IssueRuleError("Estado inválido", "status")
                validate_transition(issue["status"], data.status)
                changes["status"] = data.status.value
                changes["statusRank"] = STATUS_RANK[data.status]
            if "story_points" in provided:
                changes["storyPoints"] = validate_story_points(data.story_points)
            if "labels" in provided:
                changes["labels"] = normalize_labels(data.labels or [])
            if "acceptance_criteria" in provided:
                changes["acceptanceCriteria"] = normalize_acceptance_criteria(
                    data.acceptance_criteria or []
                )
            if "due_date" in provided:
                changes["dueDate"] = date_to_datetime(data.due_date)
            changes.update(self._block_changes(issue, data, provided))
        except IssueRuleError as error:
            raise BusinessRuleError(str(error), field=error.field) from error

        if "assignee_id" in provided:
            changes["assigneeId"] = self._valid_assignee(project, data.assignee_id)
        if "parent_issue_id" in provided:
            parent = self._load_parent(project, issue["type"], data.parent_issue_id, issue["_id"])
            changes["parentIssueId"] = parent["_id"] if parent else None
        if "depends_on_issue_ids" in provided:
            changes["dependsOnIssueIds"] = self._valid_dependencies(
                project, data.depends_on_issue_ids or [], issue["_id"]
            )
        return changes

    @staticmethod
    def _block_changes(
        issue: dict[str, Any], data: IssueUpdate, provided: set[str]
    ) -> dict[str, Any]:
        blocked = data.blocked if "blocked" in provided else issue.get("blocked", False)
        if blocked is None:
            raise IssueRuleError("Valor inválido", "blocked")
        if not blocked:
            if "block_reason" in provided and (data.block_reason or "").strip():
                raise IssueRuleError("Só uma issue bloqueada tem motivo de bloqueio", "blockReason")
            return {"blocked": False, "blockReason": None} if "blocked" in provided else {}
        if "block_reason" in provided or "blocked" in provided:
            reason = data.block_reason if "block_reason" in provided else issue.get("blockReason")
            reason = (reason or "").strip()
            if not reason:
                raise IssueRuleError("Indique o motivo do bloqueio", "blockReason")
            return {"blocked": True, "blockReason": reason}
        return {}

    def _valid_assignee(self, project: dict[str, Any], value: str | None) -> ObjectId | None:
        if not value:
            return None
        assignee_id = object_id_or_422(value, "assigneeId")
        document = self.users.find_by_ids([assignee_id]).get(assignee_id)
        is_member = assignee_id in project.get("memberIds", []) or assignee_id == project.get(
            "leadUserId"
        )
        if document is None or document.get("status") != UserStatus.ACTIVE.value or not is_member:
            raise BusinessRuleError(
                "O responsável tem de ser um utilizador ativo e membro do projeto",
                field="assigneeId",
            )
        return assignee_id

    def _load_parent(
        self,
        project: dict[str, Any],
        issue_type: IssueType | str,
        value: str | None,
        issue_id: ObjectId | None,
    ) -> dict[str, Any] | None:
        parent = None
        if value:
            parent_id = object_id_or_422(value, "parentIssueId")
            if parent_id == issue_id:
                raise BusinessRuleError(
                    "Uma issue não pode ser pai de si própria", field="parentIssueId"
                )
            parent = self.issues.find_by_id(parent_id)
            if parent is None or parent["projectId"] != project["_id"]:
                raise BusinessRuleError(
                    "A issue pai tem de existir no mesmo projeto", field="parentIssueId"
                )
        try:
            validate_parent(issue_type, parent["type"] if parent else None)
        except IssueRuleError as error:
            raise BusinessRuleError(str(error), field=error.field) from error
        return parent

    def _valid_dependencies(
        self, project: dict[str, Any], values: list[str], issue_id: ObjectId | None
    ) -> list[ObjectId]:
        ids = list(dict.fromkeys(object_id_or_422(v, "dependsOnIssueIds") for v in values))
        if issue_id is not None and issue_id in ids:
            raise BusinessRuleError(
                "Uma issue não pode depender de si própria", field="dependsOnIssueIds"
            )
        found = self.issues.find_many_by_ids(ids)
        if any(
            dep_id not in found or found[dep_id]["projectId"] != project["_id"] for dep_id in ids
        ):
            raise BusinessRuleError(
                "As dependências têm de ser issues do mesmo projeto", field="dependsOnIssueIds"
            )
        return ids

    @staticmethod
    def _ensure_not_archived(project: dict[str, Any]) -> None:
        if is_archived(project):
            raise BusinessRuleError("O projeto está arquivado e só pode ser consultado")

    @staticmethod
    def _check_version(issue: dict[str, Any], version: int) -> None:
        if issue.get("version", 1) != version:
            raise ConflictError(
                "A issue foi alterada entretanto. Recarregue e tente novamente.",
                currentVersion=issue.get("version", 1),
            )

    def require_updated(self, updated: dict[str, Any] | None, issue_id: ObjectId) -> dict[str, Any]:
        if updated is not None:
            return updated
        current = self.issues.find_by_id(issue_id)
        if current is None:
            raise NotFoundError("Issue não encontrada")
        raise ConflictError(
            "A issue foi alterada entretanto. Recarregue e tente novamente.",
            currentVersion=current.get("version", 1),
        )
