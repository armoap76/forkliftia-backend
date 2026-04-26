import pathlib
import sys

import pytest
from fastapi.testclient import TestClient


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class DummyCase:
    def __init__(self, case_id: int, status: str = "open", created_by_uid: str = "user-1"):
        self.id = case_id
        self.status = status
        self.created_by_uid = created_by_uid


class DummyStore:
    def __init__(self, case: DummyCase):
        self.case = case

    def get_case(self, case_id: int):
        return self.case if self.case.id == case_id else None

    def update_case(self, case_id: int, updates: dict):  # pragma: no cover - not used
        return self.case

    def resolve_case(self, case_id: int, resolution_note: str):  # pragma: no cover - not used
        return self.case

    def create_comment(self, case_id: int, author_uid: str, body: str):  # pragma: no cover - not used
        return {"id": 1}

    def get_comment(self, case_id: int, comment_id: int):  # pragma: no cover - not used
        return None

    def update_comment(self, case_id: int, comment_id: int, body: str):  # pragma: no cover - not used
        return None


@pytest.fixture
def client():
    from app import main

    original_store = main.store
    original_require_public_name = main.require_user_public_name
    main.app.dependency_overrides[main.get_requester_uid] = lambda: "user-1"
    main.require_user_public_name = lambda _uid: "UserOne"
    test_client = TestClient(main.app)
    yield test_client, main
    main.app.dependency_overrides.clear()
    main.require_user_public_name = original_require_public_name
    main.store = original_store


def test_comment_blocked_when_resolved(client):
    test_client, main = client
    main.store = DummyStore(DummyCase(case_id=1, status="resolved"))

    response = test_client.post("/cases/1/comments", json={"body": "hi"})

    assert response.status_code == 409
    assert response.json() == {"detail": "Case is resolved; comments are closed"}


def test_update_blocked_when_resolved(client):
    test_client, main = client
    main.store = DummyStore(DummyCase(case_id=2, status="resolved"))

    response = test_client.patch("/cases/2", json={"title": "New"})

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Case is resolved. Create a new case to continue."
    }


def test_resolve_is_idempotent(client):
    test_client, main = client
    main.store = DummyStore(DummyCase(case_id=3, status="resolved"))

    response = test_client.patch(
        "/cases/3/resolve", json={"resolution_note": "already resolved note"}
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Case is already resolved."}


def test_resolve_requires_resolution_note(client):
    test_client, main = client
    main.store = DummyStore(DummyCase(case_id=4))

    response = test_client.patch("/cases/4/resolve", json={"resolution_note": " "})

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"].startswith(
        "Value error, resolution_note must be between"
    )


def test_resolve_accepts_valid_resolution_note(client):
    test_client, main = client
    main.store = DummyStore(DummyCase(case_id=5))

    response = test_client.patch(
        "/cases/5/resolve", json={"resolution_note": "Valid note here"}
    )

    assert response.status_code == 200


def test_comment_allowed_when_open(client):
    test_client, main = client
    main.store = DummyStore(DummyCase(case_id=6))

    response = test_client.post("/cases/6/comments", json={"body": "New comment"})

    assert response.status_code == 200


def test_comment_edit_blocked_when_resolved(client):
    test_client, main = client
    main.store = DummyStore(DummyCase(case_id=7, status="resolved"))

    response = test_client.patch("/cases/7/comments/1", json={"body": "Updated"})

    assert response.status_code == 409
    assert response.json() == {"detail": "Case is resolved; comments are closed"}
