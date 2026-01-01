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


@pytest.fixture
def client():
    from app import main

    original_store = main.store
    main.app.dependency_overrides[main.get_requester_uid] = lambda: "user-1"
    test_client = TestClient(main.app)
    yield test_client, main
    main.app.dependency_overrides.clear()
    main.store = original_store


def test_comment_blocked_when_resolved(client):
    test_client, main = client
    main.store = DummyStore(DummyCase(case_id=1, status="resolved"))

    response = test_client.post("/cases/1/comments", json={"body": "hi"})

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Case is resolved. Create a new case to continue."
    }


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
        "/cases/3/resolve", json={"resolution_note": "done"}
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Case is already resolved."}
