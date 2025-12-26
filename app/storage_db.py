from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from .db_models import Case as CaseModel, User as UserModel
from .models import Case, CaseCreate
from .storage import CaseStore


class DatabaseCaseStore(CaseStore):
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def _to_case(self, db_case: CaseModel) -> Case:
        return Case(
            id=db_case.id,
            brand=db_case.brand or "unknown",
            model=db_case.model or "unknown",
            series=db_case.series,
            error_code=db_case.error_code,
            symptom=db_case.symptom or db_case.description or "N/A",
            checks_done=db_case.checks_done,
            diagnosis=db_case.diagnosis,
            status=db_case.status,
            source=db_case.source or "ai",
            tags=db_case.tags or [],
            created_at=db_case.created_at,
            updated_at=db_case.updated_at,
            resolution_note=db_case.resolution_note,
            resolved_at=db_case.resolved_at,
            created_by_uid=db_case.created_by_uid,
            closed_at=db_case.closed_at,
            title=db_case.title,
            description=db_case.description,
        )

    def _ensure_user(self, session: Session, uid: str) -> UserModel:
        user = session.query(UserModel).filter(UserModel.uid == uid).one_or_none()
        if user:
            return user

        user = UserModel(uid=uid, created_at=datetime.utcnow())
        session.add(user)
        session.flush()
        return user

    def create_case(self, data: CaseCreate) -> Case:
        with self.session_factory() as session:
            user = self._ensure_user(session, data.created_by_uid)
            now = datetime.utcnow()
            db_case = CaseModel(
                title=data.title,
                description=data.description,
                status=data.status,
                created_by_uid=user.uid,
                created_at=now,
                updated_at=now,
                brand=data.brand,
                model=data.model,
                series=data.series,
                error_code=data.error_code,
                symptom=data.symptom,
                checks_done=data.checks_done,
                diagnosis=data.diagnosis,
                source=data.source,
                tags=data.tags or [],
            )
            session.add(db_case)
            session.commit()
            session.refresh(db_case)
            return self._to_case(db_case)

    def list_cases(self, status: Optional[str] = None, limit: int = 200) -> List[Case]:
        with self.session_factory() as session:
            query = session.query(CaseModel)
            if status:
                query = query.filter(CaseModel.status == status)
            cases = query.order_by(CaseModel.id.desc()).limit(max(1, limit)).all()
            return [self._to_case(c) for c in cases]

    def get_case(self, case_id: int) -> Optional[Case]:
        with self.session_factory() as session:
            db_case = session.get(CaseModel, case_id)
            if not db_case:
                return None
            return self._to_case(db_case)

    def find_resolved_by_key(
        self,
        brand: str,
        model: str,
        series: Optional[str],
        error_code: Optional[str],
    ) -> Optional[Case]:
        if not brand or not model:
            return None

        with self.session_factory() as session:
            query = session.query(CaseModel).filter(
                CaseModel.status == "resolved",
                CaseModel.brand.ilike(brand),
                CaseModel.model.ilike(model),
            )
            if series:
                query = query.filter(CaseModel.series.ilike(series))
            if error_code:
                query = query.filter(CaseModel.error_code.ilike(error_code))

            db_case = query.order_by(CaseModel.id.desc()).first()
            if db_case:
                return self._to_case(db_case)
            return None

    def update_status(self, case_id: int, status: str) -> Optional[Case]:
        with self.session_factory() as session:
            db_case = session.get(CaseModel, case_id)
            if not db_case:
                return None

            db_case.set_status(status)
            session.commit()
            session.refresh(db_case)
            return self._to_case(db_case)

    def resolve_case(self, case_id: int, resolution_note: str) -> Optional[Case]:
        note = (resolution_note or "").strip()
        if not note:
            return None

        with self.session_factory() as session:
            db_case = session.get(CaseModel, case_id)
            if not db_case:
                return None

            db_case.mark_resolved(note)
            session.commit()
            session.refresh(db_case)
            return self._to_case(db_case)
