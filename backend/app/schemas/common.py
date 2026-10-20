from typing import Generic, TypeVar

from fastapi import Query

from app.core.errors import BusinessRuleError
from app.schemas.base import ApiModel

T = TypeVar("T")

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25


class Page(ApiModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class PageParams:
    """Parâmetros de paginação (``page`` ≥ 1, ``pageSize`` entre 1 e 100)."""

    def __init__(
        self,
        page: int = Query(default=1, ge=1, le=10_000),
        page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, alias="pageSize"),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.page_size


def parse_sort(value: str | None, allowed: dict[str, str], default: str) -> list[tuple[str, int]]:
    """Converte ``campo`` / ``-campo`` numa ordenação MongoDB estável (desempate por ``_id``).

    ``allowed`` mapeia o nome público para o campo no documento.
    """
    raw = (value or default).strip()
    direction = -1 if raw.startswith("-") else 1
    name = raw.lstrip("-+")
    if name not in allowed:
        options = ", ".join(sorted(allowed))
        raise BusinessRuleError(f"Ordenação inválida: {name}. Opções: {options}")
    return [(allowed[name], direction), ("_id", direction)]
