"""HTTP authentication endpoints for RevenueOS."""

import json
from datetime import UTC, datetime

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.authentication.services import (
    create_session,
    delete_session,
    get_user_by_username,
    validate_session,
    verify_password,
    verify_turnstile_token,
)
from apps.database.client import get_database

SESSION_COOKIE_NAME = "revenueos_session"


def get_client_ip(request: HttpRequest) -> str:
    """Extract client IP safely from request headers."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return str(x_forwarded_for).split(",")[0].strip()
    return str(request.META.get("REMOTE_ADDR", ""))


@csrf_exempt
@require_http_methods(["POST"])
def login_view(request: HttpRequest) -> JsonResponse:
    """Authenticate operator credentials with Cloudflare Turnstile and Argon2id."""
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse(
            {"error": {"code": "INVALID_REQUEST", "message": "Malformed JSON payload."}},
            status=400,
        )

    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    turnstile_token = str(body.get("turnstileToken", "")).strip()

    if not username or not password:
        return JsonResponse(
            {"error": {"code": "MISSING_CREDENTIALS", "message": "Username and password are required."}},
            status=400,
        )

    # Validate Turnstile CAPTCHA server-side
    client_ip = get_client_ip(request)
    if not turnstile_token or not verify_turnstile_token(turnstile_token, remote_ip=client_ip):
        return JsonResponse(
            {"error": {"code": "CAPTCHA_FAILED", "message": "Turnstile verification failed or missing."}},
            status=403,
        )

    # Verify user exists
    user = get_user_by_username(username)
    if not user:
        return JsonResponse(
            {"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid username or password."}},
            status=401,
        )

    # Verify Argon2id password hash
    if not verify_password(password, user.get("password_hash", "")):
        return JsonResponse(
            {"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid username or password."}},
            status=401,
        )

    # Update last_login in MongoDB
    db = get_database()
    db["users"].update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.now(UTC)}},
    )

    # Create session
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    session_token = create_session(
        user_id=user["_id"],
        username=user["username"],
        role=user.get("role", "operator"),
        ip_address=client_ip,
        user_agent=user_agent,
    )

    response = JsonResponse(
        {
            "status": "authenticated",
            "user": {
                "id": str(user["_id"]),
                "username": user["username"],
                "role": user.get("role", "operator"),
            },
        }
    )

    # Secure HTTP-only cookie
    is_secure = getattr(settings, "SESSION_COOKIE_SECURE", False)
    samesite_val = getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax")
    cookie_age = getattr(settings, "SESSION_COOKIE_AGE", 86400 * 7)

    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_token,
        max_age=cookie_age,
        httponly=True,
        secure=is_secure,
        samesite=samesite_val,
        path="/",
    )
    return response


@csrf_exempt
@require_http_methods(["POST"])
def logout_view(request: HttpRequest) -> JsonResponse:
    """Invalidate operator session and clear HTTP-only cookie."""
    session_token = request.COOKIES.get(SESSION_COOKIE_NAME, "")
    if session_token:
        delete_session(session_token)

    response = JsonResponse({"status": "logged_out"})
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@require_http_methods(["GET"])
def me_view(request: HttpRequest) -> JsonResponse:
    """Return currently authenticated operator context or 401."""
    session_token = request.COOKIES.get(SESSION_COOKIE_NAME, "")
    if not session_token:
        return JsonResponse(
            {"error": {"code": "UNAUTHORIZED", "message": "Authentication required."}},
            status=401,
        )

    session = validate_session(session_token)
    if not session:
        response = JsonResponse(
            {"error": {"code": "SESSION_EXPIRED", "message": "Session has expired or is invalid."}},
            status=401,
        )
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        return response

    return JsonResponse(
        {
            "user": {
                "id": session.get("user_id"),
                "username": session.get("username"),
                "role": session.get("role"),
            }
        }
    )
