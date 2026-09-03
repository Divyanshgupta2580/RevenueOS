"""Pytest configuration and test database fixture."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class InMemoryCollection:
    """In-memory MongoDB collection emulator for fast, isolated tests."""

    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []

    def insert_one(self, doc: dict[str, Any]) -> Any:
        import uuid
        doc_copy = dict(doc)
        if "_id" not in doc_copy:
            doc_copy["_id"] = str(uuid.uuid4())
        self.documents.append(doc_copy)
        mock_result = MagicMock()
        mock_result.inserted_id = doc_copy["_id"]
        return mock_result

    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        for doc in self.documents:
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                return dict(doc)
        return None

    def find(self, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not query:
            return [dict(d) for d in self.documents]
        res = []
        for doc in self.documents:
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                res.append(dict(doc))
        return res

    def update_one(self, query: dict[str, Any], update: dict[str, Any]) -> Any:
        doc = self.find_one(query)
        if doc and "$set" in update:
            for d in self.documents:
                if d["_id"] == doc["_id"]:
                    d.update(update["$set"])
                    break
        mock_res = MagicMock()
        mock_res.modified_count = 1 if doc else 0
        return mock_res

    def delete_one(self, query: dict[str, Any]) -> Any:
        doc = self.find_one(query)
        deleted = 0
        if doc:
            self.documents = [d for d in self.documents if d["_id"] != doc["_id"]]
            deleted = 1
        mock_res = MagicMock()
        mock_res.deleted_count = deleted
        return mock_res

    def create_index(self, *args: Any, **kwargs: Any) -> str:
        return "idx_created"


class InMemoryDatabase:
    """Mock MongoDB database returning collections on demand."""

    def __init__(self) -> None:
        self.collections: dict[str, InMemoryCollection] = {}

    def __getitem__(self, name: str) -> InMemoryCollection:
        if name not in self.collections:
            self.collections[name] = InMemoryCollection()
        return self.collections[name]


@pytest.fixture(autouse=True)
def mock_db():
    """Autouse fixture replacing PyMongo get_database with in-memory DB."""
    in_memory_db = InMemoryDatabase()
    with patch("apps.database.client.get_database", return_value=in_memory_db), \
         patch("apps.authentication.services.get_database", return_value=in_memory_db), \
         patch("apps.authentication.views.get_database", return_value=in_memory_db):
        yield in_memory_db
