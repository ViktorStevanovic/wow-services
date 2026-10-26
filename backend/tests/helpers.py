from urllib.parse import urlsplit

from httpx import AsyncClient, Response


def path_and_query(url: str) -> str:
    """`/path?query` of an absolute URL, to replay a redirect against the test client."""
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}" if parts.query else parts.path


async def sign_in(client: AsyncClient, account: str = "eu-varek") -> Response:
    """Sign in through the real mock-mode flow (dev login → callback). Returns the callback
    response; the client keeps the session cookie."""
    login = await client.get("/api/auth/dev/login", params={"account": account})
    assert login.status_code == 302, login.text
    callback = await client.get(path_and_query(login.headers["location"]))
    assert callback.status_code == 302, callback.text
    return callback
