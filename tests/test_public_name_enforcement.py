import pathlib
import sys

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def client():
    from app import main

    original_store = main.store
    original_require_public_name = main.require_user_public_name
    main.app.dependency_overrides[main.get_requester_uid] = lambda: "user-no-name"
    test_client = TestClient(main.app)
    yield test_client, main
    main.app.dependency_overrides.clear()
    main.require_user_public_name = original_require_public_name
    main.store = original_store


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/diagnosis", {
            "brand": "Linde",
            "model": "E20",
            "symptom": "No lift",
            "language": "en",
        }),
        ("post", "/cases/1/comments", {"body": "test"}),
        ("patch", "/cases/1", {"title": "Updated"}),
        ("patch", "/cases/1/resolve", {"resolution_note": "resolution note text"}),
        ("patch", "/cases/1/comments/1", {"body": "Updated comment"}),
    ],
)
def test_mutating_endpoints_require_public_name(client, method, path, payload):
    test_client, main = client

    def _raise(_uid: str):
        raise HTTPException(status_code=409, detail="PUBLIC_NAME_REQUIRED")

    main.require_user_public_name = _raise

    response = getattr(test_client, method)(path, json=payload)

    assert response.status_code == 409
    assert response.json() == {"detail": "PUBLIC_NAME_REQUIRED"}


class _FakeQuery:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return ("someone-else",)


class _FakeSession:
    def query(self, *args, **kwargs):
        return _FakeQuery()


class _FakeSessionCtx:
    def __enter__(self):
        return _FakeSession()

    def __exit__(self, exc_type, exc, tb):
        return False


def test_set_public_name_rejects_case_insensitive_duplicate(client):
    test_client, main = client

    original_get_session = main.get_session
    main.get_session = lambda: _FakeSessionCtx()

    try:
        response = test_client.put("/me/public-name", json={"public_name": "Diego"})
    finally:
        main.get_session = original_get_session

    assert response.status_code == 409
    assert response.json() == {"detail": "PUBLIC_NAME_TAKEN"}
