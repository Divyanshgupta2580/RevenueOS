"""Comprehensive negative and positive security tests for RevenueOS authentication.

Covers all 20 mandatory Phase 14 security verification requirements:
1. Login with correct credentials succeeds.
2. Login with incorrect password fails.
3. Missing username fails.
4. Missing password fails.
5. Repeated failed login attempts are rate-limited.
6. Registration succeeds with valid input.
7. Duplicate registration is rejected correctly.
8. Malformed registration fails safely.
9. Session cookie is established securely.
10. Logout invalidates session.
11. Unauthorized protected endpoint is rejected.
12. WebSocket without session is rejected.
13. WebSocket with invalid session is rejected.
14. WebSocket with valid session succeeds.
15. Invalid WebSocket origin is rejected.
16. Production origin succeeds.
17. No Turnstile token is required.
18. No Cloudflare Siteverify call occurs.
19. No Turnstile secret is loaded.
20. No Turnstile public key is loaded.
"""

import json
from unittest.mock import patch

import pytest
from django.conf import settings
from django.test import Client

from apps.authentication.services import (
    clear_account_login_failures,
    create_session,
    create_user,
    get_user_by_username,
)
from apps.authentication.views import SESSION_COOKIE_NAME
from apps.websocket.auth import WebSocketAuthMiddlewareStack
from apps.websocket.consumer import RevenueOSConsumer
from tests.test_websocket import WebsocketTestCommunicator

TEST_USER = "sec_test_operator@revenueos.internal"
TEST_PASS = "SecPassw0rd123!"


@pytest.fixture(autouse=True)
def cleanup_account():
    """Ensure clean state for the test operator before and after test."""
    clear_account_login_failures(TEST_USER)
    yield
    clear_account_login_failures(TEST_USER)


@pytest.fixture
def auth_user():
    """Seed a test operator user."""
    clear_account_login_failures(TEST_USER)
    existing = get_user_by_username(TEST_USER)
    if not existing:
        return create_user(TEST_USER, TEST_PASS, role="operator")
    return existing


# 1. Login with correct credentials succeeds
def test_1_login_with_correct_credentials_succeeds(auth_user) -> None:
    client = Client()
    res = client.post(
        "/api/auth/login/",
        data=json.dumps({"username": TEST_USER, "password": TEST_PASS}),
        content_type="application/json",
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "authenticated"
    assert data["user"]["username"] == TEST_USER
    assert SESSION_COOKIE_NAME in res.cookies


# 2. Login with incorrect password fails
def test_2_login_with_incorrect_password_fails(auth_user) -> None:
    client = Client()
    res = client.post(
        "/api/auth/login/",
        data=json.dumps({"username": TEST_USER, "password": "BadPassword999!"}),
        content_type="application/json",
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert SESSION_COOKIE_NAME not in res.cookies


# 3. Missing username fails
def test_3_missing_username_fails() -> None:
    client = Client()
    res = client.post(
        "/api/auth/login/",
        data=json.dumps({"password": TEST_PASS}),
        content_type="application/json",
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "MISSING_CREDENTIALS"


# 4. Missing password fails
def test_4_missing_password_fails(auth_user) -> None:
    client = Client()
    res = client.post(
        "/api/auth/login/",
        data=json.dumps({"username": TEST_USER}),
        content_type="application/json",
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "MISSING_CREDENTIALS"


# 5. Repeated failed login attempts are rate-limited
def test_5_repeated_failed_login_attempts_are_rate_limited(auth_user) -> None:
    client = Client()
    target_user = "brute_target@revenueos.internal"
    create_user(target_user, TEST_PASS, role="operator")
    clear_account_login_failures(target_user)

    # Trigger 5 failed attempts
    for _ in range(5):
        res = client.post(
            "/api/auth/login/",
            data=json.dumps({"username": target_user, "password": "WrongPassword!"}),
            content_type="application/json",
        )
        assert res.status_code == 401

    # 6th attempt should be blocked by account rate limiter with HTTP 429
    res_blocked = client.post(
        "/api/auth/login/",
        data=json.dumps({"username": target_user, "password": "WrongPassword!"}),
        content_type="application/json",
    )
    assert res_blocked.status_code == 429
    assert res_blocked.json()["error"]["code"] == "RATE_LIMITED"


# 6. Registration succeeds with valid input
def test_6_registration_succeeds_with_valid_input(mock_db) -> None:
    client = Client()
    email = "new_valid_op@revenueos.internal"
    res = client.post(
        "/api/auth/register/",
        data=json.dumps({
            "email": email,
            "password": "SecurePassword123!",
            "confirmPassword": "SecurePassword123!",
        }),
        content_type="application/json",
    )
    assert res.status_code == 201
    assert res.json()["status"] == "success"
    user = get_user_by_username(email)
    assert user is not None
    assert user["password_hash"].startswith("$argon2")


# 7. Duplicate registration is rejected correctly
def test_7_duplicate_registration_is_rejected(auth_user) -> None:
    client = Client()
    res = client.post(
        "/api/auth/register/",
        data=json.dumps({
            "email": TEST_USER,
            "password": "AnotherPassword123!",
            "confirmPassword": "AnotherPassword123!",
        }),
        content_type="application/json",
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "ACCOUNT_EXISTS"


# 8. Malformed registration fails safely
def test_8_malformed_registration_fails_safely() -> None:
    client = Client()
    # Non-JSON content
    res = client.post(
        "/api/auth/register/",
        data="not json payload at all",
        content_type="application/json",
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_REQUEST"

    # Missing confirmPassword
    res2 = client.post(
        "/api/auth/register/",
        data=json.dumps({"email": "test@domain.com", "password": "Password123!"}),
        content_type="application/json",
    )
    assert res2.status_code == 400
    assert res2.json()["error"]["code"] == "MISSING_FIELDS"


# 9. Session cookie is established securely
def test_9_session_cookie_is_established_securely(auth_user) -> None:
    client = Client()
    res = client.post(
        "/api/auth/login/",
        data=json.dumps({"username": TEST_USER, "password": TEST_PASS}),
        content_type="application/json",
    )
    assert res.status_code == 200
    cookie = res.cookies[SESSION_COOKIE_NAME]
    assert cookie["httponly"] is True
    assert cookie["path"] == "/"
    assert cookie["samesite"] in ("Lax", "None")


# 10. Logout invalidates session
def test_10_logout_invalidates_session(auth_user) -> None:
    client = Client()
    res = client.post(
        "/api/auth/login/",
        data=json.dumps({"username": TEST_USER, "password": TEST_PASS}),
        content_type="application/json",
    )
    token = res.cookies[SESSION_COOKIE_NAME].value

    client.cookies[SESSION_COOKIE_NAME] = token
    logout_res = client.post("/api/auth/logout/")
    assert logout_res.status_code == 200

    # Cookie cleared and subsequent request fails
    client.cookies[SESSION_COOKIE_NAME] = token
    me_res = client.get("/api/auth/me/")
    assert me_res.status_code == 401


# 11. Unauthorized protected endpoint is rejected
def test_11_unauthorized_protected_endpoint_rejected() -> None:
    client = Client()
    res = client.get("/api/auth/me/")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


# 12. WebSocket without session is rejected
@pytest.mark.asyncio
async def test_12_websocket_without_session_rejected() -> None:
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=None)
    connected, code = await communicator.connect()
    assert connected is False
    assert code == 4401


# 13. WebSocket with invalid session is rejected
@pytest.mark.asyncio
async def test_13_websocket_with_invalid_session_rejected(mock_db) -> None:
    # Use the middleware stack with an invalid cookie header
    app = WebSocketAuthMiddlewareStack(RevenueOSConsumer.as_asgi())
    headers = [(b"cookie", b"revenueos_session=invalid_nonexistent_token_hex")]
    communicator = WebsocketTestCommunicator(app, headers=headers)
    connected, code = await communicator.connect()
    assert connected is False
    assert code == 4401


# 14. WebSocket with valid session succeeds
@pytest.mark.asyncio
async def test_14_websocket_with_valid_session_succeeds(auth_user, mock_db) -> None:
    token = create_session(
        user_id=auth_user["_id"],
        username=auth_user["username"],
        role="operator",
    )
    app = WebSocketAuthMiddlewareStack(RevenueOSConsumer.as_asgi())
    headers = [(b"cookie", f"revenueos_session={token}".encode())]
    communicator = WebsocketTestCommunicator(app, headers=headers)
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.disconnect()


# 15. Invalid WebSocket origin is rejected
@pytest.mark.asyncio
async def test_15_invalid_websocket_origin_rejected(settings) -> None:
    settings.DEBUG = False
    settings.WS_ALLOWED_ORIGINS = ["https://revenueos.vercel.app"]
    user = {"id": "test_id", "username": "operator"}
    headers = [(b"origin", b"https://malicious-origin.evil.com")]
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=user, headers=headers)
    connected, code = await communicator.connect()
    assert connected is False
    assert code == 4403


# 16. Production origin succeeds
@pytest.mark.asyncio
async def test_16_production_origin_succeeds(settings) -> None:
    settings.DEBUG = False
    settings.WS_ALLOWED_ORIGINS = ["https://revenueos.vercel.app"]
    user = {"id": "test_id", "username": "operator"}
    headers = [(b"origin", b"https://revenueos.vercel.app")]
    communicator = WebsocketTestCommunicator(RevenueOSConsumer.as_asgi(), user=user, headers=headers)
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.disconnect()


# 17. No Turnstile token is required
def test_17_no_turnstile_token_required(auth_user) -> None:
    client = Client()
    payload = {"username": TEST_USER, "password": TEST_PASS}
    assert "turnstileToken" not in payload
    assert "turnstile_token" not in payload
    res = client.post("/api/auth/login/", data=json.dumps(payload), content_type="application/json")
    assert res.status_code == 200
    assert res.json()["status"] == "authenticated"


# 18. No Cloudflare Siteverify call occurs
def test_18_no_cloudflare_siteverify_call_occurs(auth_user) -> None:
    client = Client()
    with patch("requests.post") as mock_post:
        res = client.post(
            "/api/auth/login/",
            data=json.dumps({"username": TEST_USER, "password": TEST_PASS}),
            content_type="application/json",
        )
        assert res.status_code == 200
        # Assert requests.post was NEVER called (no siteverify request)
        mock_post.assert_not_called()


# 19. No Turnstile secret is loaded
def test_19_no_turnstile_secret_is_loaded() -> None:
    assert not hasattr(settings, "TURNSTILE_SECRET_KEY")
    assert not hasattr(settings, "TURNSTILE_ALLOWED_HOSTNAMES")


# 20. No Turnstile public key is loaded
def test_20_no_turnstile_public_key_is_loaded() -> None:
    assert not hasattr(settings, "TURNSTILE_SITE_KEY")
