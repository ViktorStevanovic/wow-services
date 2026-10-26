from httpx import AsyncClient


async def test_openapi_documents_error_envelope(client: AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()

    components = schema["components"]["schemas"]
    assert "ErrorResponse" in components
    assert "HTTPValidationError" not in components
    assert set(components["ErrorBody"]["properties"]) == {"code", "message", "details"}

    health = schema["paths"]["/api/health"]["get"]["responses"]
    assert health["500"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
