from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Base dos DTOs: atributos snake_case em Python, JSON em camelCase."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
