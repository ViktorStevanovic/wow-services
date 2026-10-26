from pydantic import BaseModel, ConfigDict, Field, JsonValue
from pydantic.alias_generators import to_camel

MAX_PAGE_LIMIT = 100


class BaseSchema(BaseModel):
    """Base for every DTO: camelCase on the wire, snake_case in Python."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class InputSchema(BaseSchema):
    """Base for request bodies and query models: unknown fields rejected, text stripped."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Page[T](BaseSchema):
    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=MAX_PAGE_LIMIT)
    offset: int = Field(ge=0)


class ErrorBody(BaseSchema):
    code: str = Field(description="Stable machine-readable error code.")
    message: str = Field(description="Human-readable explanation.")
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorResponse(BaseSchema):
    """Body of every non-2xx response."""

    error: ErrorBody
