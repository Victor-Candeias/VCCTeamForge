"""Hashing de passwords (Argon2id) e tokens opacos de sessão/CSRF."""

import hashlib
import hmac
import secrets
from functools import cache

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

PASSWORD_MIN_LENGTH = 12
# Limite superior evita custo excessivo de hashing com entradas enormes.
PASSWORD_MAX_LENGTH = 128

# Parâmetros mínimos recomendados pela OWASP para Argon2id (19 MiB, t=2, p=1).
_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, type=Type.ID)


class PasswordPolicyError(ValueError):
    pass


def validate_password_policy(password: str) -> None:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise PasswordPolicyError(
            f"A password tem de ter pelo menos {PASSWORD_MIN_LENGTH} caracteres"
        )
    if len(password) > PASSWORD_MAX_LENGTH:
        raise PasswordPolicyError(f"A password não pode exceder {PASSWORD_MAX_LENGTH} caracteres")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError, UnicodeEncodeError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@cache
def _dummy_hash() -> str:
    return _hasher.hash(secrets.token_urlsafe(16))


def burn_password_check(password: str) -> None:
    """Gasta o mesmo tempo que uma verificação real (utilizador inexistente)."""
    verify_password(_dummy_hash(), password)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode(), right.encode())
