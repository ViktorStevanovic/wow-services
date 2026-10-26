from http.cookies import SimpleCookie

import pytest
from httpx import AsyncClient, Response
from pydantic import SecretStr
from sqlalchemy import update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import BlizzardMode, Environment
from app.core.enums import Region
from app.core.security import OAUTH_STATE_COOKIE, SESSION_COOKIE
from app.features.users.enums import UserStatus
from app.features.users.models import User
from tests.conftest import http_client, make_settings, running_app
from tests.helpers import path_and_query, sign_in


def set_cookie(response: Response, name: str) -> dict[str, str | bool]:
    """Attributes of one Set-Cookie header, e.g. {'value': ..., 'httponly': True, ...}."""
    for header in response.headers.get_list("set-cookie"):
        cookie = SimpleCookie(header)
        if name in cookie:
            morsel = cookie[name]
            return {"value": morsel.value, **{k: v for k, v in morsel.items() if v}}
    raise AssertionError(f"no Set-Cookie for {name}")


async def test_login_redirects_with_state_cookie(client: AsyncClient) -> None:
    response = await client.get("/api/auth/battlenet/login", params={"region": "eu"})

    assert response.status_code == 302
    assert response.headers["location"].startswith(
        "http://localhost:8000/api/auth/battlenet/callback?code=mock%3Aeu-varek&state="
    )
    cookie = set_cookie(response, OAUTH_STATE_COOKIE)
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "lax"
    assert cookie["path"] == "/api/auth"
    assert "secure" not in cookie  # plain http outside production


async def test_full_sign_in_flow(client: AsyncClient) -> None:
    login = await client.get("/api/auth/battlenet/login", params={"region": "eu"})

    callback = await client.get(path_and_query(login.headers["location"]))

    assert callback.status_code == 302
    assert callback.headers["location"] == "http://localhost:3000"
    session = set_cookie(callback, SESSION_COOKIE)
    assert session["httponly"] is True
    assert session["samesite"] == "lax"
    assert session["path"] == "/"
    assert session["max-age"] == str(30 * 24 * 3600)
    assert set_cookie(callback, OAUTH_STATE_COOKIE)["max-age"] == "0"  # state cookie cleared

    me = await client.get("/api/me")
    assert me.status_code == 200
    body = me.json()
    assert set(body) == {
        "id",
        "region",
        "battletag",
        "language",
        "status",
        "createdAt",
        "lastSignInAt",
    }
    assert (body["region"], body["battletag"], body["status"]) == ("eu", "Varek#2101", "active")


async def test_callback_never_exposes_blizzard_token(client: AsyncClient) -> None:
    callback = await sign_in(client)

    assert "mock-token" not in str(callback.headers)
    assert "mock-token" not in (await client.get("/api/me")).text


async def test_logout(client: AsyncClient) -> None:
    await sign_in(client)

    response = await client.post("/api/auth/logout")

    assert response.status_code == 204
    assert set_cookie(response, SESSION_COOKIE)["max-age"] == "0"
    # Even if a client kept the old cookie, the session is gone server-side.
    assert (await client.get("/api/me")).status_code == 401


async def test_logout_when_signed_out(client: AsyncClient) -> None:
    assert (await client.post("/api/auth/logout")).status_code == 204


async def test_me_requires_sign_in(client: AsyncClient) -> None:
    response = await client.get("/api/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_me_with_unknown_cookie(client: AsyncClient) -> None:
    client.cookies.set(SESSION_COOKIE, "forged")

    assert (await client.get("/api/me")).status_code == 401


async def test_me_suspended_user(client: AsyncClient, db_session: AsyncSession) -> None:
    await sign_in(client)
    await db_session.exec(update(User).values(status=UserStatus.SUSPENDED))

    response = await client.get("/api/me")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_suspended"


async def test_callback_with_wrong_state(client: AsyncClient) -> None:
    login = await client.get("/api/auth/battlenet/login", params={"region": "eu"})
    tampered = path_and_query(login.headers["location"]).replace("state=", "state=x")

    response = await client.get(tampered)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "oauth_state_invalid"
    assert SESSION_COOKIE not in response.headers.get("set-cookie", "")


async def test_callback_without_state_cookie(client: AsyncClient) -> None:
    login = await client.get("/api/auth/battlenet/login", params={"region": "eu"})
    client.cookies.clear()

    response = await client.get(path_and_query(login.headers["location"]))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "oauth_state_invalid"


async def test_callback_cancelled_on_battlenet(client: AsyncClient) -> None:
    login = await client.get("/api/auth/battlenet/login", params={"region": "eu"})
    state = path_and_query(login.headers["location"]).split("state=")[1]

    response = await client.get(
        "/api/auth/battlenet/callback", params={"error": "access_denied", "state": state}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "battlenet_login_cancelled"


async def test_login_with_invalid_region(client: AsyncClient) -> None:
    response = await client.get("/api/auth/battlenet/login", params={"region": "cn"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_login_with_unsupported_region(db_session: AsyncSession) -> None:
    settings = make_settings(blizzard_regions=[Region.US])
    async with running_app(settings, db_session) as app, http_client(app) as client:
        response = await client.get("/api/auth/battlenet/login", params={"region": "eu"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "region_not_supported"


async def test_dev_accounts(client: AsyncClient) -> None:
    response = await client.get("/api/auth/dev/accounts")

    assert response.status_code == 200
    varek = next(a for a in response.json() if a["key"] == "eu-varek")
    assert varek["characterNames"][0] == "Morgath Ashveil"


async def test_dev_login_as_chosen_account(client: AsyncClient) -> None:
    await sign_in(client, "us-dorin")

    assert (await client.get("/api/me")).json()["battletag"] == "Dorin#7788"


async def test_dev_login_unknown_account(client: AsyncClient) -> None:
    response = await client.get("/api/auth/dev/login", params={"account": "nobody"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "dev_account_not_found"


@pytest.mark.parametrize("path", ["/api/auth/dev/accounts", "/api/auth/dev/login?account=x"])
async def test_dev_endpoints_hidden_in_live_mode(db_session: AsyncSession, path: str) -> None:
    settings = make_settings(
        blizzard_mode=BlizzardMode.LIVE,
        blizzard_client_id="id",
        blizzard_client_secret=SecretStr("secret"),
        blizzard_profile_namespace="p-{region}",
        blizzard_static_namespace="s-{region}",
    )
    async with running_app(settings, db_session) as app, http_client(app) as client:
        response = await client.get(path)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_cookies_are_secure_in_production(db_session: AsyncSession) -> None:
    settings = make_settings(environment=Environment.PRODUCTION)
    async with (
        running_app(settings, db_session) as app,
        http_client(app, base_url="https://test.local") as client,
    ):
        login = await client.get("/api/auth/battlenet/login", params={"region": "eu"})
        callback = await client.get(path_and_query(login.headers["location"]))

    assert set_cookie(login, OAUTH_STATE_COOKIE)["secure"] is True
    assert set_cookie(callback, SESSION_COOKIE)["secure"] is True
