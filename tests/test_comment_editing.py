import pathlib
import sys
from datetime import datetime

import pytest
from fastapi.testclient import TestClient


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class DummyCase:
    def __init__(self, case_id: int, status: str = "open", created_by_uid: str = "owner"):
        self.id = case_id
        self.status = status
        self.created_by_uid = created_by_uid


class DummyComment:
    def __init__(self, comment_id: int, case_id: int, author_uid: str, body: str = "Body"):
        self.id = comment_id
        self.case_id = case_id
        self.author_uid = author_uid
        self.author_public_name = None
        self.body = body
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()


class DummyStore:
    def __init__(self, case: DummyCase | None, comment: DummyComment | None):
        self.case = case
        self.comment = comment
        self.updated_body = None

    def get_case(self, case_id: int):
        return self.case if self.case and self.case.id == case_id else None

    def get_comment(self, case_id: int, comment_id: int):
        if not self.comment:
            return None
        if self.comment.case_id == case_id and self.comment.id == comment_id:
            return self.comment
        return None

    def update_comment(self, case_id: int, comment_id: int, body: str):
        comment = self.get_comment(case_id, comment_id)
        if not comment:
            return None
        self.updated_body = body
        comment.body = body
        comment.updated_at = datetime.utcnow()
        return comment


@pytest.fixture
def client():
    from app import main

    original_store = main.store
    original_admin_uids = set(main.ADMIN_UIDS)
    original_require_public_name = main.require_user_public_name
    main.app.dependency_overrides[main.get_requester_uid] = lambda: "author-1"
    main.require_user_public_name = lambda _uid: "AuthorOne"
    test_client = TestClient(main.app)
    yield test_client, main
    main.app.dependency_overrides.clear()
    main.ADMIN_UIDS.clear()
    main.ADMIN_UIDS.update(original_admin_uids)
    main.require_user_public_name = original_require_public_name
    main.store = original_store


def test_edit_comment_404_when_case_missing(client):
    test_client, main = client
    main.store = DummyStore(case=None, comment=None)

    response = test_client.patch("/cases/999/comments/1", json={"body": "Updated"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Case not found"}


def test_edit_comment_404_when_comment_missing(client):
    test_client, main = client
    main.store = DummyStore(case=DummyCase(case_id=1), comment=None)

    response = test_client.patch("/cases/1/comments/99", json={"body": "Updated"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Comment not found"}


def test_edit_comment_forbidden_for_non_author_non_admin(client):
    test_client, main = client
    main.store = DummyStore(
        case=DummyCase(case_id=1),
        comment=DummyComment(comment_id=2, case_id=1, author_uid="someone-else"),
    )

    response = test_client.patch("/cases/1/comments/2", json={"body": "Updated"})

    assert response.status_code == 403
    assert response.json() == {"detail": "Not authorized to modify this comment"}


def test_edit_comment_allowed_for_author(client):
    test_client, main = client
    main.store = DummyStore(
        case=DummyCase(case_id=1),
        comment=DummyComment(comment_id=2, case_id=1, author_uid="author-1", body="Old"),
    )

    response = test_client.patch("/cases/1/comments/2", json={"body": "Updated"})

    assert response.status_code == 200
    assert response.json()["body"] == "Updated"


def test_edit_comment_allowed_for_admin(client):
    test_client, main = client
    main.ADMIN_UIDS.add("admin-1")
    main.app.dependency_overrides[main.get_requester_uid] = lambda: "admin-1"
    main.store = DummyStore(
        case=DummyCase(case_id=1),
        comment=DummyComment(comment_id=2, case_id=1, author_uid="author-1", body="Old"),
    )

    response = test_client.patch("/cases/1/comments/2", json={"body": "Updated by admin"})

    assert response.status_code == 200
    assert response.json()["body"] == "Updated by admin"
