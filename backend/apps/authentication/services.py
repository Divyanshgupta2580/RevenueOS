"""Authentication services for RevenueOS.

Includes Argon2id password hashing, sliding-window rate limiting,
per-account failure cooldown protection, and PyMongo-backed session management.
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from apps.core.exceptions import AuthenticationError
from apps.database.client import get_database

logger = logging.getLogger(__name__)

ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(plain_password: str) -> str:
    """Hash password using Argon2id."""
    if not plain_password or len(plain_password) < 8:
        raise AuthenticationError("Password must be at least 8 characters.")
    return ph.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against stored Argon2id hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


_rate_limit_records: dict[str, list[float]] = {}
_account_failure_records: dict[str, list[float]] = {}


def check_rate_limit(key: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    """Sliding-window rate limiter per key (e.g. IP address or action:IP)."""
    now = datetime.now(UTC).timestamp()
    cutoff = now - window_seconds
    timestamps = _rate_limit_records.get(key, [])
    valid_timestamps = [t for t in timestamps if t > cutoff]
    if len(valid_timestamps) >= max_requests:
        _rate_limit_records[key] = valid_timestamps
        return False
    valid_timestamps.append(now)
    _rate_limit_records[key] = valid_timestamps
    return True


def check_account_rate_limit(username: str, max_failures: int = 5, window_seconds: int = 300) -> bool:
    """Check if an account has exceeded maximum allowed failed login attempts.

    Provides brute-force and credential-stuffing protection on a per-account basis
    independent of client IP or network origin.
    """
    if not username:
        return True
    key = username.strip().lower()
    now = datetime.now(UTC).timestamp()
    cutoff = now - window_seconds
    timestamps = _account_failure_records.get(key, [])
    valid_timestamps = [t for t in timestamps if t > cutoff]
    _account_failure_records[key] = valid_timestamps
    return len(valid_timestamps) < max_failures


def record_account_login_failure(username: str, window_seconds: int = 300) -> None:
    """Record a failed login attempt for account cooldown tracking."""
    if not username:
        return
    key = username.strip().lower()
    now = datetime.now(UTC).timestamp()
    cutoff = now - window_seconds
    timestamps = _account_failure_records.get(key, [])
    valid_timestamps = [t for t in timestamps if t > cutoff]
    valid_timestamps.append(now)
    _account_failure_records[key] = valid_timestamps


def clear_account_login_failures(username: str) -> None:
    """Clear failed login attempts upon successful authentication."""
    if not username:
        return
    key = username.strip().lower()
    _account_failure_records.pop(key, None)


def reset_rate_limits() -> None:
    """Clear all in-memory rate limit records (for testing isolation and maintenance)."""
    _rate_limit_records.clear()
    _account_failure_records.clear()



def create_user(username: str, plain_password: str, role: str = "operator") -> dict[str, Any]:
    """Create a new user with Argon2id hashed password in MongoDB."""
    db = get_database()
    users_col = db["users"]

    normalized_username = username.strip().lower()
    existing = users_col.find_one({"username": normalized_username})
    if existing:
        raise AuthenticationError("Username already exists.")

    pw_hash = hash_password(plain_password)
    user_doc = {
        "username": normalized_username,
        "password_hash": pw_hash,
        "role": role,
        "created_at": datetime.now(UTC),
        "last_login": None,
    }
    result = users_col.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id
    return user_doc


def get_user_by_username(username: str) -> dict[str, Any] | None:
    """Retrieve user document by username."""
    db = get_database()
    return db["users"].find_one({"username": username.strip().lower()})


def create_session(
    user_id: Any,
    username: str,
    role: str,
    ip_address: str = "",
    user_agent: str = "",
    ttl_days: int = 7,
) -> str:
    """Create a cryptographically secure session in MongoDB."""
    db = get_database()
    sessions_col = db["sessions"]

    session_token = secrets.token_hex(32)
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=ttl_days)

    session_doc = {
        "session_token": session_token,
        "user_id": str(user_id),
        "username": username,
        "role": role,
        "created_at": now,
        "expires_at": expires_at,
        "ip_address": ip_address,
        "user_agent": user_agent,
    }
    sessions_col.insert_one(session_doc)
    return session_token


def validate_session(session_token: str) -> dict[str, Any] | None:
    """Validate session token against MongoDB and verify it is not expired."""
    if not session_token:
        return None

    db = get_database()
    session = db["sessions"].find_one({"session_token": session_token})
    if not session:
        return None

    expires_at = session.get("expires_at")
    if isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            db["sessions"].delete_one({"session_token": session_token})
            return None

    if session:
        return dict(session)
    return None


def delete_session(session_token: str) -> bool:
    """Delete session token on logout."""
    if not session_token:
        return False
    db = get_database()
    res = db["sessions"].delete_one({"session_token": session_token})
    return res.deleted_count > 0
