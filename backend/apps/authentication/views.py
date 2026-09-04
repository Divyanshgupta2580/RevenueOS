"""HTTP authentication endpoints for RevenueOS."""

import json
import re
from datetime import UTC, datetime

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.authentication.services import (
    check_rate_limit,
    create_session,
    create_user,
    delete_session,
    get_user_by_username,
    validate_session,
    verify_password,
    verify_turnstile_token,
)
from apps.database.client import get_database

SESSION_COOKIE_NAME = "revenueos_session"
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def _cors_response(request: HttpRequest, response: HttpResponse) -> HttpResponse:
    """Attach standard CORS headers to support cross-port browser authentication."""
    origin = request.META.get("HTTP_ORIGIN") or getattr(settings, "FRONTEND_ORIGIN", "http://localhost:3000")
    response["Access-Control-Allow-Origin"] = origin
    response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    response["Access-Control-Allow-Credentials"] = "true"
    return response


def get_client_ip(request: HttpRequest) -> str:
    """Extract client IP safely from request headers."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return str(x_forwarded_for).split(",")[0].strip()
    return str(request.META.get("REMOTE_ADDR", ""))


@csrf_exempt
def register_view(request: HttpRequest) -> HttpResponse:
    """Register a new operator account with Argon2id password hashing and Turnstile verification."""
    if request.method == "OPTIONS":
        return _cors_response(request, HttpResponse(status=200))

    if request.method != "POST":
        return _cors_response(
            request,
            JsonResponse({"error": {"code": "METHOD_NOT_ALLOWED", "message": "Only POST is allowed."}}, status=405),
        )
    client_ip = get_client_ip(request)
    if not check_rate_limit(f"register:{client_ip}", max_requests=10, window_seconds=60):
        return _cors_response(
            request,
            JsonResponse(
                {"error": {"code": "RATE_LIMITED", "message": "Too many registration attempts. Please wait a moment before trying again."}},
                status=429,
            ),
        )

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return _cors_response(
            request,
            JsonResponse(
                {"error": {"code": "INVALID_REQUEST", "message": "Malformed JSON payload."}},
                status=400,
            ),
        )

    email = str(body.get("email") or body.get("username", "")).strip().lower()
    password = str(body.get("password", ""))
    confirm_password = str(body.get("confirmPassword") or body.get("confirm_password", ""))
    turnstile_token = str(body.get("turnstileToken") or body.get("turnstile_token", "")).strip()

    if not email or not password or not confirm_password:
        return _cors_response(
            request,
            JsonResponse(
                {"error": {"code": "MISSING_FIELDS", "message": "Email, password, and password confirmation are required."}},
                status=400,
            ),
        )

    if not EMAIL_REGEX.match(email):
        return _cors_response(
            request,
            JsonResponse(
                {"error": {"code": "INVALID_EMAIL", "message": "Please enter a valid email address."}},
                status=400,
            ),
        )

    if len(password) < 8:
        return _cors_response(
            request,
            JsonResponse(
                {"error": {"code": "WEAK_PASSWORD", "message": "Password must be at least 8 characters long."}},
                status=400,
            ),
        )

    if password != confirm_password:
        return _cors_response(
            request,
            JsonResponse(
                {"error": {"code": "PASSWORD_MISMATCH", "message": "Passwords do not match."}},
                status=400,
            ),
        )

    if not turnstile_token or not verify_turnstile_token(turnstile_token, remote_ip=client_ip):
        return _cors_response(
            request,
            JsonResponse(
                {"error": {"code": "CAPTCHA_FAILED", "message": "Turnstile verification failed or is missing."}},
                status=403,
            ),
        )

    # Safe duplicate user check
    existing_user = get_user_by_username(email)
    if existing_user:
        return _cors_response(
            request,
            JsonResponse(
                {
                    "error": {
                        "code": "ACCOUNT_EXISTS",
                        "message": "An account with this email address already exists. Please sign in or use another email.",
                    }
                },
                status=409,
            ),
        )

    try:
        new_user = create_user(username=email, plain_password=password, role="operator")
    except Exception:
        return _cors_response(
            request,
            JsonResponse(
                {"error": {"code": "REGISTRATION_ERROR", "message": "Failed to create account."}},
                status=500,
            ),
        )

    return _cors_response(
        request,
        JsonResponse(
            {
                "status": "success",
                "message": "Account registered successfully. Please sign in with your credentials.",
                "user": {
                    "id": str(new_user["_id"]),
                    "username": new_user["username"],
                    "role": new_user["role"],
                },
            },
            status=201,
        ),
    )


@csrf_exempt
def login_view(request: HttpRequest) -> HttpResponse:
    """Authenticate operator credentials with Cloudflare Turnstile and Argon2id."""
    if request.method == "OPTIONS":
        return _cors_response(request, HttpResponse(status=200))

    if request.method != "POST":
        return _cors_response(
            request,
            JsonResponse({"error": {"code": "METHOD_NOT_ALLOWED", "message": "Only POST is allowed."}}, status=405),
        )

    client_ip = get_client_ip(request)
    if not check_rate_limit(f"login:{client_ip}", max_requests=15, window_seconds=60):
        return _cors_response(
            request,
            JsonResponse(
                {"error": {"code": "RATE_LIMITED", "message": "Too many login attempts. Please wait before trying again."}},
                status=429,
            ),
        )

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return _cors_response(
            request,
            JsonResponse(
                {"error": {"code": "INVALID_REQUEST", "message": "Malformed JSON payload."}},
                status=400,
            ),
        )

    username = str(body.get("username") or body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))
    turnstile_token = str(body.get("turnstileToken") or body.get("turnstile_token", "")).strip()

    if not username or not password:
        return _cors_response(
            request,
            JsonResponse(
                {"error": {"code": "MISSING_CREDENTIALS", "message": "Username and password are required."}},
                status=400,
            ),
        )

    # Validate Turnstile CAPTCHA server-side
    if not turnstile_token or not verify_turnstile_token(turnstile_token, remote_ip=client_ip):
        return _cors_response(
            request,
            JsonResponse(
                {"error": {"code": "CAPTCHA_FAILED", "message": "Turnstile verification failed or missing."}},
                status=403,
            ),
        )

    # Verify user exists
    user = get_user_by_username(username)
    if not user:
        return _cors_response(
            request,
            JsonResponse(
                {"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid username or password."}},
                status=401,
            ),
        )

    # Verify Argon2id password hash
    if not verify_password(password, user.get("password_hash", "")):
        return _cors_response(
            request,
            JsonResponse(
                {"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid username or password."}},
                status=401,
            ),
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
    return _cors_response(request, response)


@csrf_exempt
def logout_view(request: HttpRequest) -> HttpResponse:
    """Invalidate operator session and clear HTTP-only cookie."""
    if request.method == "OPTIONS":
        return _cors_response(request, HttpResponse(status=200))

    if request.method != "POST":
        return _cors_response(
            request,
            JsonResponse({"error": {"code": "METHOD_NOT_ALLOWED", "message": "Only POST is allowed."}}, status=405),
        )

    session_token = request.COOKIES.get(SESSION_COOKIE_NAME, "")
    if session_token:
        delete_session(session_token)

    response = JsonResponse({"status": "logged_out"})
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return _cors_response(request, response)


@csrf_exempt
def me_view(request: HttpRequest) -> HttpResponse:
    """Return currently authenticated operator context or 401."""
    if request.method == "OPTIONS":
        return _cors_response(request, HttpResponse(status=200))

    if request.method != "GET":
        return _cors_response(
            request,
            JsonResponse({"error": {"code": "METHOD_NOT_ALLOWED", "message": "Only GET is allowed."}}, status=405),
        )

    session_token = request.COOKIES.get(SESSION_COOKIE_NAME, "")
    if not session_token:
        return _cors_response(
            request,
            JsonResponse(
                {"error": {"code": "UNAUTHORIZED", "message": "Authentication required."}},
                status=401,
            ),
        )

    session = validate_session(session_token)
    if not session:
        response = JsonResponse(
            {"error": {"code": "SESSION_EXPIRED", "message": "Session has expired or is invalid."}},
            status=401,
        )
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        return _cors_response(request, response)

    return _cors_response(
        request,
        JsonResponse(
            {
                "user": {
                    "id": session.get("user_id"),
                    "username": session.get("username"),
                    "role": session.get("role"),
                }
            }
        ),
    )
