"""Direct PyMongo database connection manager and index initializer."""

import logging
from typing import Any

from django.conf import settings
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

logger = logging.getLogger("revenueos.database")
_mongo_client: MongoClient | None = None


def get_mongo_client() -> MongoClient:
    """Return the singleton MongoClient instance with resilient timeout settings."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=4000,
            connectTimeoutMS=4000,
            socketTimeoutMS=5000,
            maxPoolSize=20,
            minPoolSize=1,
            retryWrites=True,
        )
    return _mongo_client


def get_database() -> Database:
    """Return the configured MongoDB database instance."""
    client = get_mongo_client()
    return client[settings.MONGODB_DB]


def ping_database() -> bool:
    """Ping MongoDB Atlas to verify connection health."""
    try:
        client = get_mongo_client()
        client.admin.command("ping")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.warning(f"MongoDB health ping failed: {exc}")
        return False
    except Exception as exc:
        logger.error(f"Unexpected MongoDB error during ping: {exc}")
        return False


def close_mongo_connection() -> None:
    """Safely close the MongoClient connection."""
    global _mongo_client
    if _mongo_client is not None:
        try:
            _mongo_client.close()
        except Exception:
            pass
        _mongo_client = None


def init_database_indexes(db: Any | None = None) -> dict[str, list[str]]:
    """Create essential unique and search indexes across the 6 required collections.

    Indexes are selected carefully to optimize lookup, TTL expiration, and idempotency
    without wasteful memory overhead on the free tier.
    """
    if db is None:
        db = get_database()

    created_indexes: dict[str, list[str]] = {}

    try:
        # 1. users: unique lookup on username
        db["users"].create_index([("username", ASCENDING)], unique=True)
        created_indexes["users"] = ["username_1"]

        # 2. sessions: unique session_token and TTL on expires_at
        db["sessions"].create_index([("session_token", ASCENDING)], unique=True)
        db["sessions"].create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
        created_indexes["sessions"] = ["session_token_1", "expires_at_1"]

        # 3. payments: unique payment_id, compound status + updated_at
        db["payments"].create_index([("payment_id", ASCENDING)], unique=True)
        db["payments"].create_index([("status", ASCENDING), ("updated_at", DESCENDING)])
        db["payments"].create_index([("recovery_status", ASCENDING)])
        created_indexes["payments"] = ["payment_id_1", "status_1_updated_at_-1", "recovery_status_1"]

        # 4. recovery_decisions: unique decision_id, lookup by payment_id
        db["recovery_decisions"].create_index([("decision_id", ASCENDING)], unique=True)
        db["recovery_decisions"].create_index([("payment_id", ASCENDING), ("created_at", DESCENDING)])
        created_indexes["recovery_decisions"] = ["decision_id_1", "payment_id_1_created_at_-1"]

        # 5. recovery_actions: unique action_id, unique idempotency_key
        db["recovery_actions"].create_index([("action_id", ASCENDING)], unique=True)
        db["recovery_actions"].create_index([("idempotency_key", ASCENDING)], unique=True)
        db["recovery_actions"].create_index([("payment_id", ASCENDING)])
        created_indexes["recovery_actions"] = ["action_id_1", "idempotency_key_1", "payment_id_1"]

        # 6. webhook_events: unique event_id for strict webhook idempotency
        db["webhook_events"].create_index([("event_id", ASCENDING)], unique=True)
        db["webhook_events"].create_index([("payment_id", ASCENDING)])
        created_indexes["webhook_events"] = ["event_id_1", "payment_id_1"]

        logger.info("Successfully initialized MongoDB indexes.")
    except Exception as exc:
        logger.warning(f"Note: MongoDB index creation encountered an issue: {exc}")

    return created_indexes
