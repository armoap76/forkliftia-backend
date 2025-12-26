from __future__ import annotations

import json
import os
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db_models import Base, Case as CaseModel, User as UserModel

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/forkliftia",
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


LEGACY_USER_UID = "legacy-import"


def ensure_user(session, uid: str) -> UserModel:
    user = session.query(UserModel).filter(UserModel.uid == uid).one_or_none()
    if user:
        return user

    user = UserModel(uid=uid, created_at=datetime.utcnow())
    session.add(user)
    session.flush()
    return user


def import_cases(path: str) -> None:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise RuntimeError("Invalid cases.json format")

    with SessionLocal() as session:
        ensure_user(session, LEGACY_USER_UID)
        session.commit()

    for raw in cases:
        migrate_case(raw)



def migrate_case(raw_case: dict) -> None:
    with SessionLocal() as session:
        ensure_user(session, LEGACY_USER_UID)

        title = raw_case.get("title") or f"Case #{raw_case.get('id')}"
        description = raw_case.get("description") or raw_case.get("symptom") or ""
        created_at = _parse_dt(raw_case.get("created_at"))
        updated_at = _parse_dt(raw_case.get("updated_at"))
        resolved_at = _parse_dt(raw_case.get("resolved_at"))
        closed_at = _parse_dt(raw_case.get("closed_at"))

        db_case = CaseModel(
            title=title,
            description=description,
            status=raw_case.get("status", "open"),
            created_by_uid=raw_case.get("created_by_uid") or LEGACY_USER_UID,
            created_at=created_at or datetime.utcnow(),
            updated_at=updated_at or datetime.utcnow(),
            closed_at=closed_at,
            brand=raw_case.get("brand"),
            model=raw_case.get("model"),
            series=raw_case.get("series"),
            error_code=raw_case.get("error_code"),
            symptom=raw_case.get("symptom"),
            checks_done=raw_case.get("checks_done"),
            diagnosis=raw_case.get("diagnosis"),
            source=raw_case.get("source"),
            tags=raw_case.get("tags") or [],
            resolution_note=raw_case.get("resolution_note"),
            resolved_at=resolved_at,
        )

        session.add(db_case)
        session.commit()
        print(f"Imported case {db_case.id}: {db_case.title}")


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import legacy cases.json into the database")
    parser.add_argument("--path", default="app/data/cases.json", help="Path to cases.json")
    args = parser.parse_args()

    Base.metadata.create_all(engine)
    import_cases(args.path)
