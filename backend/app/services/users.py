import re
from datetime import UTC, datetime

from bson import ObjectId
from pymongo.database import Database

from app.core.security import hash_password, validate_password_policy
from app.domain.permissions import Role
from app.domain.users import User
from app.repositories.audit import AuditLogRepository
from app.repositories.users import UserRepository

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserService:
    def __init__(self, db: Database) -> None:
        self.users = UserRepository(db)
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
        if not _EMAIL_PATTERN.match(email.strip()) or len(email) > 254:
            raise ValueError("Email inválido")
        if not name.strip():
            raise ValueError("O nome é obrigatório")
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
