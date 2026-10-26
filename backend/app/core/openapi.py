from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.core.schemas import ErrorResponse

_FASTAPI_VALIDATION_REF = "#/components/schemas/HTTPValidationError"
_ERROR_RESPONSE_REF = f"#/components/schemas/{ErrorResponse.__name__}"


def install_openapi(app: FastAPI) -> None:
    """Document 422 responses with our error envelope instead of FastAPI's default schema."""

    def openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        for path_item in schema.get("paths", {}).values():
            for operation in path_item.values():
                response = operation.get("responses", {}).get("422")
                if response is None:
                    continue
                json_schema = response["content"]["application/json"]["schema"]
                if json_schema.get("$ref") == _FASTAPI_VALIDATION_REF:
                    json_schema["$ref"] = _ERROR_RESPONSE_REF
        components = schema.get("components", {}).get("schemas", {})
        components.pop("HTTPValidationError", None)
        components.pop("ValidationError", None)
        app.openapi_schema = schema
        return schema

    app.openapi = openapi  # type: ignore[method-assign]  # FastAPI's documented override hook
