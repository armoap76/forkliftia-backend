import base64
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# Helper to build an unsigned JWT for testing purposes

def _make_token(sub: str, extra: dict | None = None) -> str:
    header = {"alg": "none", "typ": "JWT"}
    payload = {"sub": sub}
    if extra:
        payload.update(extra)

    def _encode(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    return f"{_encode(header)}.{_encode(payload)}."


def test_extract_uid_uses_sub_when_firebase_unavailable(monkeypatch):
    from app import main

    # Ensure we exercise the fallback path
    monkeypatch.setattr(main, "firebase_auth", None)
    monkeypatch.setattr(main, "firebase_admin", None)

    token = _make_token("user-123")
    assert main.extract_uid_from_token(token) == "user-123"


def test_extract_uid_is_stable_for_same_subject(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "firebase_auth", None)
    monkeypatch.setattr(main, "firebase_admin", None)

    token_one = _make_token("same-user", {"iat": 1})
    token_two = _make_token("same-user", {"iat": 999})

    assert main.extract_uid_from_token(token_one) == "same-user"
    assert main.extract_uid_from_token(token_two) == "same-user"
