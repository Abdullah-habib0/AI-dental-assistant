"""Rate limits and CORS."""

from httpx import ASGITransport, AsyncClient

from app.core import rate_limiting
from app.main import app
from tests.test_chat import EchoHistory, use_agent

LOGIN = "/api/v1/auth/login"
WRONG_LOGIN = {"email": "nobody@example.com", "password": "wrong-password"}


async def test_chat_allows_ten_messages_a_minute_then_says_wait(client, monkeypatch):
    use_agent(monkeypatch, EchoHistory())
    for _ in range(10):
        assert (await client.post("/api/v1/chat", json={"message": "hi"})).status_code == 200

    r = await client.post("/api/v1/chat", json={"message": "hi"})
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0


async def test_login_attempts_are_limited(client):
    for _ in range(5):
        assert (await client.post(LOGIN, json=WRONG_LOGIN)).status_code == 401
    assert (await client.post(LOGIN, json=WRONG_LOGIN)).status_code == 429


async def test_each_visitor_has_their_own_limit(client):
    for _ in range(5):
        await client.post(LOGIN, json=WRONG_LOGIN)
    assert (await client.post(LOGIN, json=WRONG_LOGIN)).status_code == 429

    other = ASGITransport(app=app, client=("10.0.0.2", 5000))
    async with AsyncClient(transport=other, base_url="http://test") as someone_else:
        assert (await someone_else.post(LOGIN, json=WRONG_LOGIN)).status_code == 401


async def test_the_window_slides_so_old_requests_stop_counting(client, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(rate_limiting.time, "monotonic", lambda: clock[0])

    for _ in range(5):
        await client.post(LOGIN, json=WRONG_LOGIN)
    assert (await client.post(LOGIN, json=WRONG_LOGIN)).status_code == 429

    clock[0] += 61  # a minute later, the old attempts have left the window
    assert (await client.post(LOGIN, json=WRONG_LOGIN)).status_code == 401


async def test_cheap_pages_are_not_limited(client):
    for _ in range(30):
        assert (await client.get("/api/v1/services")).status_code == 200


async def test_cors_allows_the_frontend_and_no_one_else(client):
    preflight = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}

    allowed = await client.options("/api/v1/chat", headers={"Origin": "http://localhost:3000", **preflight})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"

    other = await client.options("/api/v1/chat", headers={"Origin": "https://evil.example", **preflight})
    assert "access-control-allow-origin" not in other.headers


# --- Visitors arriving through the website's server ---------------------------------


async def test_the_websites_visitor_address_is_trusted_only_with_the_secret(client, monkeypatch):
    """Logged-in requests all come from the website's server. With the right secret its
    X-Visitor-IP is believed, so each visitor still gets their own limit; without it, a
    made-up address must not let anyone dodge the limit."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "frontend_secret", "shared-test-secret")
    through_website = {"x-frontend-secret": "shared-test-secret"}

    for _ in range(5):
        await client.post(LOGIN, json=WRONG_LOGIN, headers={**through_website, "x-visitor-ip": "203.0.113.1"})
    blocked = await client.post(LOGIN, json=WRONG_LOGIN, headers={**through_website, "x-visitor-ip": "203.0.113.1"})
    assert blocked.status_code == 429

    # Another visitor through the same website server is counted separately.
    other = await client.post(LOGIN, json=WRONG_LOGIN, headers={**through_website, "x-visitor-ip": "203.0.113.2"})
    assert other.status_code == 401


async def test_a_wrong_or_missing_secret_means_the_address_is_ignored(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "frontend_secret", "shared-test-secret")
    for _ in range(5):
        await client.post(LOGIN, json=WRONG_LOGIN)
    # Pretending to be someone else, with a guessed secret or none, doesn't reset the count.
    for headers in ({"x-visitor-ip": "198.51.100.7"},
                    {"x-visitor-ip": "198.51.100.7", "x-frontend-secret": "guess"}):
        assert (await client.post(LOGIN, json=WRONG_LOGIN, headers=headers)).status_code == 429
