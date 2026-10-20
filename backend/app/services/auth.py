import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.database import Database

from app.core.config import Settings
from app.core.errors import TooManyRequestsError, UnauthorizedError
from app.core.security import (
    burn_password_check,
    hash_password,
    hash_token,
    new_token,
    password_needs_rehash,
    verify_password,
)
from app.domain.users import User, normalize_email
from app.repositories.audit import AuditLogRepository
from app.repositories.login_attempts import LoginAttemptRepository
from app.repositories.sessions import SessionRepository
from app.repositories.users import UserRepository

# Evita uma escrita na BD por pedido: a expiração por inatividade só é renovada após este intervalo.
SESSION_TOUCH_INTERVAL = timedelta(minutes=1)
INVALID_CREDENTIALS = "Email ou password inválidos"


@dataclass(frozen=True)
class LoginResult:
    user: User
    session_token: str
    csrf_token: str


@dataclass(frozen=True)
class AuthenticatedSession:
    session: dict[str, Any]
    user: User


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AuthService:
    def __init__(
        self, db: Database, settings: Settings, clock: Callable[[], datetime] = _utcnow
    ) -> None:
        self.settings = settings
        self.clock = clock
        self.users = UserRepository(db)
        self.sessions = SessionRepository(db)
        self.attempts = LoginAttemptRepository(db)
        self.audit = AuditLogRepository(db)
        self.idle_timeout = timedelta(minutes=settings.session_idle_minutes)
        self.absolute_timeout = timedelta(hours=settings.session_absolute_hours)

    def login(
        self, email: str, password: str, *, ip: str | None, user_agent: str | None
    ) -> LoginResult:
        now = self.clock()
        email_key = f"email:{normalize_email(email)}"
        ip_key = f"ip:{ip}" if ip else None
        self._check_rate_limit(email_key, ip_key, now)

        document = self.users.find_by_email(email)
        if document is None:
            burn_password_check(password)
            valid = False
        else:
            valid = verify_password(document["passwordHash"], password)
        user = User.from_document(document) if document else None

        if not valid or user is None or not user.is_active:
            self.attempts.record_failure([key for key in (email_key, ip_key) if key], now)
            self.audit.record(
                "auth.login_failed",
                now=now,
                actor_id=user.id if user else None,
                entity_type="user",
                entity_id=user.id if user else None,
                ip=ip,
                details={
                    "email": normalize_email(email),
                    "reason": "disabled" if valid and user else "invalid_credentials",
                },
            )
            raise UnauthorizedError(INVALID_CREDENTIALS)

        new_hash = (
            hash_password(password) if password_needs_rehash(document["passwordHash"]) else None
        )
        self.users.record_login(user.id, now, new_hash)
        self.attempts.clear(email_key)

        session_token, csrf_token = new_token(), new_token()
        self.sessions.create(
            user_id=user.id,
            token_hash=hash_token(session_token),
            csrf_token_hash=hash_token(csrf_token),
            now=now,
            idle_timeout=self.idle_timeout,
            absolute_timeout=self.absolute_timeout,
            ip=ip,
            user_agent=user_agent,
        )
        self.audit.record(
            "auth.login", now=now, actor_id=user.id, entity_type="user", entity_id=user.id, ip=ip
        )
        return LoginResult(user=user, session_token=session_token, csrf_token=csrf_token)

    def _check_rate_limit(self, email_key: str, ip_key: str | None, now: datetime) -> None:
        window = timedelta(minutes=self.settings.login_window_minutes)
        limits = [(email_key, self.settings.login_max_failures_per_email)]
        if ip_key:
            limits.append((ip_key, self.settings.login_max_failures_per_ip))
        for key, limit in limits:
            failures = self.attempts.failures_since(key, now - window)
            if len(failures) >= limit:
                # O pedido volta a ser aceite quando a falha mais antiga relevante sair da janela.
                retry_after = failures[-limit] + window - now
                raise TooManyRequestsError(
                    "Demasiadas tentativas falhadas. Tente novamente mais tarde.",
                    retry_after=max(1, math.ceil(retry_after.total_seconds())),
                )

    def authenticate(self, session_token: str) -> AuthenticatedSession | None:
        now = self.clock()
        session = self.sessions.find_active(hash_token(session_token), now)
        if session is None:
            return None
        document = self.users.find_by_id(session["userId"])
        user = User.from_document(document) if document else None
        if user is None or not user.is_active:
            self.sessions.delete(session["_id"])
            return None
        if now - session["lastSeenAt"] >= SESSION_TOUCH_INTERVAL:
            self.sessions.extend(session, now, self.idle_timeout)
        return AuthenticatedSession(session=session, user=user)

    def logout(self, auth: AuthenticatedSession, *, ip: str | None) -> None:
        now = self.clock()
        self.sessions.delete(auth.session["_id"])
        self.audit.record(
            "auth.logout",
            now=now,
            actor_id=auth.user.id,
            entity_type="user",
            entity_id=auth.user.id,
            ip=ip,
        )
