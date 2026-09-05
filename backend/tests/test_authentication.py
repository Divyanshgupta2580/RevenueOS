"""Acceptance tests for Authentication & Session Management."""

import json

import pytest
from django.test import Client

from apps.authentication.services import create_session, create_user
from apps.authentication.views import SESSION_COOKIE_NAME

TEST_USERNAME = "operator@revenueos.internal"
TEST_PASSWORD = "ValidPassword1234!"


@pytest.fixture
def seeded_user():
    """Create a verified test user."""
    return create_user(TEST_USERNAME, TEST_PASSWORD, role="operator")


def test_valid_login(seeded_user) -> None:
    """Acceptance Test: VALID LOGIN with Argon2id password verification and session issuance."""
    client = Client()
    payload = {
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
    }
    response = client.post(
        "/api/auth/login/",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "authenticated"
    assert data["user"]["username"] == TEST_USERNAME
    assert data["user"]["role"] == "operator"

    # Verify secrets never leak in the response
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]

    # Verify secure HTTP-only cookie was issued
    assert SESSION_COOKIE_NAME in response.cookies
    cookie = response.cookies[SESSION_COOKIE_NAME]
    assert cookie["httponly"] is True
    assert cookie["samesite"] in ["Lax", "None"]


def test_invalid_password(seeded_user) -> None:
    """Acceptance Test: INVALID PASSWORD returns 401."""
    client = Client()
    payload = {
        "username": TEST_USERNAME,
        "password": "WrongPassword999!",
    }
    response = client.post(
        "/api/auth/login/",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "INVALID_CREDENTIALS"
    assert SESSION_COOKIE_NAME not in response.cookies


def test_expired_session(seeded_user, mock_db) -> None:
    """Acceptance Test: EXPIRED SESSION is rejected and deleted."""
    client = Client()

    # Create an expired session in MongoDB
    expired_token = create_session(
        user_id=seeded_user["_id"],
        username=seeded_user["username"],
        role="operator",
        ttl_days=-1,  # Expired yesterday
    )

    client.cookies[SESSION_COOKIE_NAME] = expired_token
    response = client.get("/api/auth/me/")

    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "SESSION_EXPIRED"


def test_logout(seeded_user) -> None:
    """Acceptance Test: LOGOUT invalidates session and clears cookie."""
    client = Client()

    # Log in first
    login_payload = {
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
    }
    login_res = client.post(
        "/api/auth/login/",
        data=json.dumps(login_payload),
        content_type="application/json",
    )
    assert login_res.status_code == 200
    token = login_res.cookies[SESSION_COOKIE_NAME].value

    # Perform logout
    client.cookies[SESSION_COOKIE_NAME] = token
    logout_res = client.post("/api/auth/logout/")
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "logged_out"

    # Verify session is now invalidated
    client.cookies[SESSION_COOKIE_NAME] = token
    me_res = client.get("/api/auth/me/")
    assert me_res.status_code == 401


def test_unauthenticated_access() -> None:
    """Acceptance Test: UNAUTHENTICATED ACCESS returns 401."""
    client = Client()
    response = client.get("/api/auth/me/")
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"


def test_authenticated_access(seeded_user) -> None:
    """Acceptance Test: AUTHENTICATED ACCESS returns user profile."""
    client = Client()

    session_token = create_session(
        user_id=seeded_user["_id"],
        username=seeded_user["username"],
        role="operator",
    )

    client.cookies[SESSION_COOKIE_NAME] = session_token
    response = client.get("/api/auth/me/")

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["username"] == TEST_USERNAME
    assert data["user"]["role"] == "operator"
    assert "password_hash" not in data["user"]


def test_registration_success(mock_db) -> None:
    """Acceptance Test: Successful registration creates user with Argon2id hash."""
    client = Client()
    payload = {
        "email": "new.operator@revenueos.internal",
        "password": "StrongPassword123!",
        "confirmPassword": "StrongPassword123!",
    }
    response = client.post(
        "/api/auth/register/",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["user"]["username"] == "new.operator@revenueos.internal"
    assert "password" not in data["user"]

    # Verify user exists in database with Argon2id hash and NO plaintext password
    from apps.authentication.services import get_user_by_username
    user = get_user_by_username("new.operator@revenueos.internal")
    assert user is not None
    assert "password" not in user
    assert user["password_hash"].startswith("$argon2")

    # Verify no session cookie was manufactured automatically
    assert SESSION_COOKIE_NAME not in response.cookies


def test_registration_weak_password() -> None:
    """Acceptance Test: Password < 8 characters is rejected."""
    client = Client()
    payload = {
        "email": "operator.short@revenueos.internal",
        "password": "short",
        "confirmPassword": "short",
    }
    response = client.post(
        "/api/auth/register/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "WEAK_PASSWORD"


def test_registration_password_mismatch() -> None:
    """Acceptance Test: Non-matching passwords are rejected."""
    client = Client()
    payload = {
        "email": "operator.mismatch@revenueos.internal",
        "password": "Password1234!",
        "confirmPassword": "DifferentPassword1234!",
    }
    response = client.post(
        "/api/auth/register/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PASSWORD_MISMATCH"


def test_registration_invalid_email() -> None:
    """Acceptance Test: Malformed email is rejected."""
    client = Client()
    payload = {
        "email": "not-an-email",
        "password": "Password1234!",
        "confirmPassword": "Password1234!",
    }
    response = client.post(
        "/api/auth/register/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_EMAIL"


def test_registration_duplicate_email(seeded_user) -> None:
    """Acceptance Test: Duplicate registration is safely rejected with 409."""
    client = Client()
    payload = {
        "email": TEST_USERNAME,
        "password": "AnotherPassword123!",
        "confirmPassword": "AnotherPassword123!",
    }
    response = client.post(
        "/api/auth/register/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ACCOUNT_EXISTS"


def test_registration_to_login_flow(mock_db) -> None:
    """Acceptance Test: Complete Register -> Login -> Me user journey."""
    client = Client()
    email = "flow.test@revenueos.internal"
    password = "FlowPassword999!"

    # 1. Register
    reg_res = client.post(
        "/api/auth/register/",
        data=json.dumps({
            "email": email,
            "password": password,
            "confirmPassword": password,
        }),
        content_type="application/json",
    )
    assert reg_res.status_code == 201

    # 2. Login with registered credentials
    login_res = client.post(
        "/api/auth/login/",
        data=json.dumps({
            "username": email,
            "password": password,
        }),
        content_type="application/json",
    )
    assert login_res.status_code == 200
    assert SESSION_COOKIE_NAME in login_res.cookies

    # 3. Check /api/auth/me/
    token = login_res.cookies[SESSION_COOKIE_NAME].value
    client.cookies[SESSION_COOKIE_NAME] = token
    me_res = client.get("/api/auth/me/")
    assert me_res.status_code == 200
    assert me_res.json()["user"]["username"] == email
