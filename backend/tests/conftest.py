"""Pytest configuration and test database fixture."""

import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class InMemoryCursor:
    """Mock PyMongo Cursor with sort, skip, limit, and iteration."""

    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._docs = documents

    def sort(self, key: Any, direction: int = 1) -> "InMemoryCursor":
        return self

    def skip(self, count: int) -> "InMemoryCursor":
        self._docs = self._docs[count:]
        return self

    def limit(self, count: int) -> "InMemoryCursor":
        self._docs = self._docs[:count]
        return self

    def __iter__(self):
        return iter(self._docs)

    def __len__(self) -> int:
        return len(self._docs)


class InMemoryCollection:
    """In-memory MongoDB collection emulator for fast, isolated tests."""

    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []

    def insert_one(self, doc: dict[str, Any]) -> Any:
        doc_copy = dict(doc)
        if "_id" not in doc_copy:
            doc_copy["_id"] = str(uuid.uuid4())
        self.documents.append(doc_copy)
        mock_result = MagicMock()
        mock_result.inserted_id = doc_copy["_id"]
        return mock_result

    def find_one(
        self,
        query: dict[str, Any],
        projection: dict[str, int] | None = None,
    ) -> dict[str, Any] | None:
        for doc in self.documents:
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                res = dict(doc)
                if projection and projection.get("_id") == 0 and "_id" in res:
                    del res["_id"]
                return res
        return None

    def find(
        self,
        query: dict[str, Any] | None = None,
        projection: dict[str, int] | None = None,
    ) -> InMemoryCursor:
        matched: list[dict[str, Any]] = []
        for doc in self.documents:
            if not query:
                matched.append(dict(doc))
                continue
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                matched.append(dict(doc))

        if projection and projection.get("_id") == 0:
            for d in matched:
                if "_id" in d:
                    del d["_id"]

        return InMemoryCursor(matched)

    def count_documents(self, query: dict[str, Any]) -> int:
        return len(self.find(query))

    def find_one_and_update(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        projection: dict[str, int] | None = None,
        return_document: bool = True,
    ) -> dict[str, Any] | None:
        doc = self.find_one(query)
        if not doc:
            return None
        if "$inc" in update:
            for k, v in update["$inc"].items():
                for d in self.documents:
                    if d.get("payment_id") == query.get("payment_id"):
                        d[k] = d.get(k, 0) + v
                        doc[k] = d[k]
        return doc

    def update_one(self, query: dict[str, Any], update: dict[str, Any]) -> Any:
        doc = self.find_one(query)
        if doc and "$set" in update:
            for d in self.documents:
                match = True
                for k, v in query.items():
                    if d.get(k) != v:
                        match = False
                        break
                if match:
                    d.update(update["$set"])
                    break
        mock_res = MagicMock()
        mock_res.modified_count = 1 if doc else 0
        return mock_res

    def update_many(self, query: dict[str, Any], update: dict[str, Any]) -> Any:
        count = 0
        if "$set" in update:
            for d in self.documents:
                match = True
                for k, v in query.items():
                    if d.get(k) != v:
                        match = False
                        break
                if match:
                    d.update(update["$set"])
                    count += 1
        mock_res = MagicMock()
        mock_res.modified_count = count
        return mock_res

    def delete_one(self, query: dict[str, Any]) -> Any:
        doc = self.find_one(query)
        deleted = 0
        if doc:
            self.documents = [d for d in self.documents if d.get("_id") != doc.get("_id")]
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

    def __getattr__(self, name: str) -> InMemoryCollection:
        return self[name]


@pytest.fixture(autouse=True)
def mock_db():
    """Autouse fixture replacing PyMongo get_database with in-memory DB."""
    in_memory_db = InMemoryDatabase()
    with patch("apps.database.client.get_database", return_value=in_memory_db), \
         patch("apps.database.repositories.get_database", return_value=in_memory_db), \
         patch("apps.webhooks.processor.get_database", return_value=in_memory_db), \
         patch("apps.authentication.services.get_database", return_value=in_memory_db), \
         patch("apps.authentication.views.get_database", return_value=in_memory_db):
        yield in_memory_db
