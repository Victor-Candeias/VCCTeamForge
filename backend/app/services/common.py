from datetime import UTC, date, datetime, time
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from app.core.errors import BusinessRuleError


def object_id_or_422(value: str, field: str) -> ObjectId:
    """IDs recebidos no corpo do pedido: inválido → 422 (nos caminhos de URL usa-se 404)."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as error:
        raise BusinessRuleError(f"Identificador inválido em {field}", field=field) from error


def date_to_datetime(value: date | None) -> datetime | None:
    """O BSON não tem tipo data: guarda-se a meia-noite UTC."""
    return datetime.combine(value, time.min, tzinfo=UTC) if value else None


def datetime_to_date(value: datetime | None) -> date | None:
    return value.date() if value else None


def jsonable(value: Any) -> Any:
    """Valores para guardar em auditoria/histórico de forma legível."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    return value
