import re
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.core.security import PasswordPolicyError, hash_password, validate_password_policy
from app.domain.permissions import Role
from app.domain.users import User, UserStatus
from app.repositories.audit import AuditLogRepository
from app.repositories.sessions import SessionRepository
from app.repositories.users import EmailAlreadyExistsError, UserRepository
from app.schemas.common import PageParams
from app.schemas.users import PasswordReset, UserAdminResponse, UserCreate, UserUpdate

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

USER_SORT_FIELDS = {
    "name": "name",
    "email": "normalizedEmail",
    "createdAt": "createdAt",
    "lastLoginAt": "lastLoginAt",
}

_TRACKED_FIELDS = ("name", "email", "role", "status")
_STALE_MESSAGE = "O utilizador foi alterado entretanto. Recarregue e tente novamente."


def _validate_email(email: str) -> None:
    if not _EMAIL_PATTERN.match(email.strip()) or len(email) > 254:
        raise ValueError("Email inválido")


def _validate_name(name: str) -> None:
    if not name.strip():
        raise ValueError("O nome é obrigatório")


class UserService:
    def __init__(self, db: Database) -> None:
        self.users = UserRepository(db)
        self.sessions = SessionRepository(db)
        self.audit = AuditLogRepository(db)

    def create_user(
        self,
        *,
        email: str,
        name: str,
        role: Role,
        password: str,
        actor_id: ObjectId | None = None,
        source: str = "api",
    ) -> User:
        """Cria um utilizador ativo. Lança ``ValueError`` ou ``EmailAlreadyExistsError``."""
        _validate_email(email)
        _validate_name(name)
        validate_password_policy(password)
        now = datetime.now(UTC)
        document = self.users.create(
            email=email, name=name, role=role, password_hash=hash_password(password), now=now
        )
        user = User.from_document(document)
        self.audit.record(
            "user.created",
            now=now,
            actor_id=actor_id,
            entity_type="user",
            entity_id=user.id,
            details={"role": role.value, "source": source},
        )
        return user

    # Gestão pelo Administrador (DEV-028) ----------------------------------------------------

    def search(
        self,
        *,
        text: str | None,
        roles: list[Role],
        statuses: list[UserStatus],
        sort: list[tuple[str, int]],
        page: PageParams,
    ) -> tuple[list[UserAdminResponse], int]:
        query: dict[str, Any] = {}
        if roles:
            query["role"] = {"$in": [role.value for role in roles]}
        if statuses:
            query["status"] = {"$in": [status.value for status in statuses]}
        if text and text.strip():
            pattern = re.escape(text.strip())
            query["$or"] = [
                {"name": {"$regex": pattern, "$options": "i"}},
                {"normalizedEmail": {"$regex": pattern, "$options": "i"}},
            ]
        documents = self.users.search(query, sort=sort, skip=page.skip, limit=page.page_size)
        return [UserAdminResponse.from_document(doc) for doc in documents], self.users.count(query)

    def get(self, user_id: ObjectId) -> UserAdminResponse:
        return UserAdminResponse.from_document(self._get_document(user_id))

    def create(self, actor: User, data: UserCreate) -> UserAdminResponse:
        for field, validate, value in (
            ("email", _validate_email, data.email),
            ("name", _validate_name, data.name),
            ("password", validate_password_policy, data.password),
        ):
            try:
                validate(value)
            except ValueError as error:
                raise BusinessRuleError(str(error), field=field) from None
        try:
            user = self.create_user(
                email=data.email,
                name=data.name,
                role=data.role,
                password=data.password,
                actor_id=actor.id,
            )
        except EmailAlreadyExistsError:
            raise ConflictError("Já existe um utilizador com este email", field="email") from None
        return self.get(user.id)

    def update(self, actor: User, user_id: ObjectId, data: UserUpdate) -> UserAdminResponse:
        document = self._get_document(user_id)
        provided = data.model_fields_set - {"version"}
        changes: dict[str, Any] = {}

        if "name" in provided:
            name = (data.name or "").strip()
            if not name:
                raise BusinessRuleError("O nome é obrigatório", field="name")
            changes["name"] = name
        if "email" in provided:
            email = (data.email or "").strip()
            try:
                _validate_email(email)
            except ValueError as error:
                raise BusinessRuleError(str(error), field="email") from None
            changes["email"] = email
        if "role" in provided:
            if data.role is None:
                raise BusinessRuleError("Perfil inválido", field="role")
            changes["role"] = data.role.value
        if "status" in provided:
            if data.status is None:
                raise BusinessRuleError("Estado inválido", field="status")
            changes["status"] = data.status.value

        if user_id == actor.id:
            # Garante que fica sempre pelo menos um administrador ativo (o próprio).
            if changes.get("role", document["role"]) != document["role"]:
                raise BusinessRuleError("Não pode alterar o seu próprio perfil", field="role")
            if changes.get("status", document.get("status")) != document.get("status"):
                raise BusinessRuleError("Não pode desativar a sua própria conta", field="status")

        diff = {
            field: {"from": document.get(field), "to": value}
            for field, value in changes.items()
            if field in _TRACKED_FIELDS and document.get(field) != value
        }
        if not diff:
            self._check_version(document, data.version)
            return UserAdminResponse.from_document(document)

        now = datetime.now(UTC)
        try:
            updated = self.users.update_versioned(
                user_id, data.version, now=now, set_fields={key: changes[key] for key in diff}
            )
        except EmailAlreadyExistsError:
            raise ConflictError("Já existe um utilizador com este email", field="email") from None
        updated = self._require_updated(updated, user_id)
        if "status" in diff and updated["status"] == UserStatus.DISABLED.value:
            self.sessions.delete_for_user(user_id)
        self._audit("user.updated", actor, user_id, now, {"changes": diff})
        return UserAdminResponse.from_document(updated)

    def reset_password(
        self,
        actor: User,
        user_id: ObjectId,
        data: PasswordReset,
        *,
        current_session_id: ObjectId | None = None,
    ) -> UserAdminResponse:
        document = self._get_document(user_id)
        self._check_version(document, data.version)
        try:
            validate_password_policy(data.password)
        except PasswordPolicyError as error:
            raise BusinessRuleError(str(error), field="password") from None
        now = datetime.now(UTC)
        updated = self.users.update_versioned(
            user_id,
            data.version,
            now=now,
            set_fields={"passwordHash": hash_password(data.password), "passwordChangedAt": now},
        )
        updated = self._require_updated(updated, user_id)
        keep = current_session_id if user_id == actor.id else None
        ended = self.sessions.delete_for_user(user_id, except_session_id=keep)
        self._audit("user.password_reset", actor, user_id, now, {"sessionsEnded": ended})
        return UserAdminResponse.from_document(updated)

    # Auxiliares -----------------------------------------------------------------------------

    def _get_document(self, user_id: ObjectId) -> dict[str, Any]:
        document = self.users.find_by_id(user_id)
        if document is None:
            raise NotFoundError("Utilizador não encontrado")
        return document

    @staticmethod
    def _check_version(document: dict[str, Any], version: int) -> None:
        if document.get("version", 1) != version:
            raise ConflictError(_STALE_MESSAGE, currentVersion=document.get("version", 1))

    def _require_updated(self, updated: dict[str, Any] | None, user_id: ObjectId) -> dict[str, Any]:
        if updated is not None:
            return updated
        current = self._get_document(user_id)
        raise ConflictError(_STALE_MESSAGE, currentVersion=current.get("version", 1))

    def _audit(
        self, action: str, actor: User, user_id: ObjectId, now: datetime, details: dict[str, Any]
    ) -> None:
        self.audit.record(
            action,
            now=now,
            actor_id=actor.id,
            entity_type="user",
            entity_id=user_id,
            details=details,
        )
