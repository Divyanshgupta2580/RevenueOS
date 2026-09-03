"""Direct PyMongo database connection manager."""


from django.conf import settings
from pymongo import MongoClient
from pymongo.database import Database

_mongo_client: MongoClient | None = None


def get_mongo_client() -> MongoClient:
    """Return the singleton MongoClient instance."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
        )
    return _mongo_client


def get_database() -> Database:
    """Return the configured MongoDB database."""
    client = get_mongo_client()
    return client[settings.MONGODB_DB]


def close_mongo_connection() -> None:
    """Safely close the MongoClient connection."""
    global _mongo_client
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
